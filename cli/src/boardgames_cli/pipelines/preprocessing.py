from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Iterable

import polars as pl
from tqdm.auto import tqdm

from boardgames_cli.config import (
    PreprocessingConfig,
    PreprocessingFilters,
    TokenizationConfig,
)

logger = logging.getLogger(__name__)


_TOKEN_PATTERN = re.compile(r"[a-z0-9']+")

_COLUMN_RENAMING = {
    "BGGId": "bgg_id",
    "Name": "name",
    "Description": "description",
    "YearPublished": "year_published",
    "AvgRating": "avg_rating",
    "NumOwned": "num_owned",
    "MinPlayers": "min_players",
    "MaxPlayers": "max_players",
    "ComMaxPlaytime": "community_max_playtime",
    "ComMinPlaytime": "community_min_playtime",
    "MfgPlaytime": "mfg_playtime",
    "NumUserRatings": "num_user_ratings",
    "GameWeight": "complexity",
    "ComAgeRec": "age_recommendation",
}


class _SynonymNormalizer:
    def __init__(self, config: TokenizationConfig, synonyms: dict[str, list[str]] | None) -> None:
        self._enabled = config.unify_synonyms and bool(synonyms)
        self._patterns: list[tuple[re.Pattern[str], str]] = []
        if not self._enabled or not synonyms:
            return
        for canonical, variants in synonyms.items():
            canonical_value = self._canonicalize(canonical)
            entries = set(v.lower() for v in variants)
            entries.add(canonical.lower())
            for variant in sorted(entries, key=len, reverse=True):
                if not variant.strip():
                    continue
                pattern = re.compile(rf"\b{re.escape(self._canonicalize(variant))}\b")
                self._patterns.append((pattern, canonical_value))

    @staticmethod
    def _canonicalize(value: str) -> str:
        cleaned = value.lower().replace("-", " ").replace("/", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def normalize(self, text: str) -> str:
        if not self._enabled:
            return text
        normalized = re.sub(r"\s+", " ", text)
        for pattern, replacement in self._patterns:
            normalized = pattern.sub(replacement, normalized)
        return normalized


def preprocess_data(
    *,
    directory: Path,
    stopwords: set[str],
    config: PreprocessingConfig,
    synonyms: dict[str, list[str]] | None = None,
    show_progress: bool = False,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    directory = directory.resolve()
    stopword_lookup = {word.lower() for word in stopwords}
    progress = tqdm(
        total=4,
        desc="Preprocessing data",
        unit="stage",
        disable=not show_progress,
    )
    try:
        logger.info("Loading raw files from %s", directory)
        games = _load_games(directory)
        categories = _extract_category_flags(games)
        mechanics = _load_tag_table(directory / "mechanics.csv", "mechanics")
        subcategories = _load_tag_table(directory / "subcategories.csv", "subcategories")
        themes = _load_tag_table(directory / "themes.csv", "themes")
        progress.update(1)

        if show_progress:
            logger.info("Enriching dataset with supplementary tags")
        enriched = (
            games.drop([column for column in games.columns if column.startswith("cat_")])
            .join(categories, on="bgg_id", how="left")
            .join(subcategories, on="bgg_id", how="left")
            .join(mechanics, on="bgg_id", how="left")
            .join(themes, on="bgg_id", how="left")
            .with_columns(
                # Community reports track actual table pace better than marketing claims.
                pl.coalesce(
                    pl.col("community_max_playtime"),
                    pl.col("community_min_playtime"),
                    pl.col("mfg_playtime"),
                ).alias("playing_time_minutes"),
            )
        )

        enriched = enriched.with_columns(
            pl.concat_str(
                [pl.col("categories"), pl.col("subcategories")],
                separator=", ",
                ignore_nulls=True,
            ).alias("categories"),
        )
        progress.update(1)

        if show_progress:
            logger.info("Applying configured filters")
        filtered, filters_report = _apply_filters(enriched, config.filters)
        progress.update(1)

        if show_progress:
            logger.info("Assembling feature table")
        features = _assemble_feature_table(
            frame=filtered,
            config=config,
            stopwords=stopword_lookup,
            synonyms=synonyms,
        )
        progress.update(1)

    finally:
        progress.close()

    quality_report = _build_quality_report(
        raw_games=games,
        filtered=filtered,
        features=features,
        filters_report=filters_report,
        config=config,
    )
    return features, quality_report


def _read_csv(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required dataset '{path.name}' not found at {path}.")
    return pl.read_csv(path)


def _load_games(directory: Path) -> pl.DataFrame:
    games = _read_csv(directory / "games.csv")
    missing = [column for column in _COLUMN_RENAMING if column not in games.columns]
    if missing:
        raise ValueError("games.csv missing required columns: " + ", ".join(sorted(missing)))
    renamed = games.rename(_COLUMN_RENAMING)
    category_columns = [column for column in games.columns if column.startswith("Cat:")]
    rename_categories = {
        column: f"cat_{column.split(':', 1)[1].strip().lower().replace(' ', '_')}"
        for column in category_columns
    }
    renamed = renamed.rename(rename_categories)
    return renamed


def _extract_category_flags(frame: pl.DataFrame) -> pl.DataFrame:
    category_columns = [column for column in frame.columns if column.startswith("cat_")]
    if not category_columns:
        # Keep schema aligned with primary table to avoid join type mismatches.
        bgg_dtype = frame.schema.get("bgg_id", pl.Int64)
        return pl.DataFrame(
            {
                "bgg_id": pl.Series([], dtype=bgg_dtype),
                "categories": pl.Series([], dtype=pl.Utf8),
            }
        )
    melted = frame.select(["bgg_id", *category_columns]).unpivot(
        index="bgg_id",
        on=category_columns,
        variable_name="category",
        value_name="flag",
    )
    return (
        melted.filter(pl.col("flag") > 0)
        .with_columns(pl.col("category").str.replace("cat_", ""))
        .group_by("bgg_id")
        .agg(pl.col("category").sort().str.join(", "))
        .rename({"category": "categories"})
    )


def _load_tag_table(path: Path, output_column: str) -> pl.DataFrame:
    table = _read_csv(path)
    if "BGGId" not in table.columns:
        raise ValueError(f"{path.name} is missing 'BGGId' column")
    value_columns = [column for column in table.columns if column != "BGGId"]
    melted = table.rename({"BGGId": "bgg_id"}).unpivot(
        index="bgg_id",
        on=value_columns,
        variable_name="tag",
        value_name="flag",
    )
    return (
        melted.filter(pl.col("flag") > 0)
        .group_by("bgg_id")
        .agg(pl.col("tag").sort().str.join(", "))
        .rename({"tag": output_column})
    )


def _apply_filters(
    frame: pl.DataFrame,
    filters: PreprocessingFilters,
) -> tuple[pl.DataFrame, list[dict[str, Any]]]:
    report: list[dict[str, Any]] = []
    current = frame

    if filters.max_year is not None:
        # Very new titles rarely have stable rating signals yet.
        before = current.height
        current = current.filter(
            pl.col("year_published").is_null() | (pl.col("year_published") <= filters.max_year)
        )
        report.append(
            {
                "name": "max_year",
                "value": filters.max_year,
                "before_rows": before,
                "after_rows": current.height,
                "removed": before - current.height,
            }
        )

    popularity_column = "num_user_ratings"
    if filters.min_popularity_quantile > 0.0:
        if popularity_column not in current.columns:
            raise ValueError("num_user_ratings column missing for popularity filtering")
        threshold_series = current.select(
            pl.col(popularity_column)
            .fill_null(0)
            .cast(pl.Float64)
            .quantile(filters.min_popularity_quantile)
        )
        threshold = float(threshold_series.item()) if threshold_series.height else 0.0
        before = current.height
        current = current.filter(pl.col(popularity_column).fill_null(0) >= threshold)
        report.append(
            {
                "name": "min_popularity_quantile",
                "value": filters.min_popularity_quantile,
                "threshold": threshold,
                "before_rows": before,
                "after_rows": current.height,
                "removed": before - current.height,
            }
        )

    if filters.min_avg_rating:
        popularity_override_expr, popularity_details = _popularity_override(current, filters)
        effective_override_expr = (
            popularity_override_expr if popularity_override_expr is not None else pl.lit(False)
        )
        kept_by_override = current.filter(
            (pl.col("avg_rating") < filters.min_avg_rating) & effective_override_expr
        ).height
        before = current.height
        current = current.filter(
            (pl.col("avg_rating") >= filters.min_avg_rating) | effective_override_expr
        )
        entry: dict[str, Any] = {
            "name": "min_avg_rating",
            "value": filters.min_avg_rating,
            "before_rows": before,
            "after_rows": current.height,
            "removed": before - current.height,
        }
        if popularity_override_expr is not None:
            entry["popularity_override"] = {
                **popularity_details,
                "kept_by_override": kept_by_override,
            }
        report.append(entry)

    before = current.height
    current = current.filter(
        pl.col("min_players").is_null() | (pl.col("min_players") <= filters.max_required_players)
    )
    report.append(
        {
            "name": "max_required_players",
            "value": filters.max_required_players,
            "before_rows": before,
            "after_rows": current.height,
            "removed": before - current.height,
        }
    )

    before = current.height
    current = current.filter(
        pl.col("playing_time_minutes").is_null()
        | (pl.col("playing_time_minutes") <= filters.max_playing_time_minutes)
    )
    report.append(
        {
            "name": "max_playing_time_minutes",
            "value": filters.max_playing_time_minutes,
            "before_rows": before,
            "after_rows": current.height,
            "removed": before - current.height,
        }
    )
    return current, report


def _popularity_override(
    frame: pl.DataFrame, filters: PreprocessingFilters
) -> tuple[pl.Expr | None, dict[str, Any]]:
    expressions: list[pl.Expr] = []
    details: dict[str, Any] = {}

    if filters.popularity_override_min_num_ratings > 0:
        if "num_user_ratings" not in frame.columns:
            logger.warning(
                "num_user_ratings column missing; popularity override by ratings will be skipped"
            )
        else:
            expressions.append(
                pl.col("num_user_ratings").fill_null(0)
                >= filters.popularity_override_min_num_ratings
            )
            details["min_num_user_ratings"] = filters.popularity_override_min_num_ratings

    if filters.popularity_override_top_owned_quantile > 0.0:
        if "num_owned" not in frame.columns:
            logger.warning(
                "num_owned column missing; popularity override by ownership will be skipped"
            )
        else:
            threshold_series = frame.select(
                pl.col("num_owned")
                .fill_null(0)
                .cast(pl.Float64)
                .quantile(filters.popularity_override_top_owned_quantile)
            )
            owned_threshold = float(threshold_series.item()) if threshold_series.height else 0.0
            expressions.append(pl.col("num_owned").fill_null(0) >= owned_threshold)
            details["owned_quantile"] = filters.popularity_override_top_owned_quantile
            details["owned_threshold"] = owned_threshold

    if not expressions:
        return None, details
    return pl.any_horizontal(expressions), details


def _build_quality_report(
    *,
    raw_games: pl.DataFrame,
    filtered: pl.DataFrame,
    features: pl.DataFrame,
    filters_report: list[dict[str, Any]],
    config: PreprocessingConfig,
) -> dict[str, Any]:
    filters_with_rates: list[dict[str, Any]] = []
    for entry in filters_report:
        before_rows = entry.get("before_rows", 0) or 0
        removed = entry.get("removed", 0) or 0
        removal_rate = (removed / before_rows) if before_rows else 0.0
        filters_with_rates.append(
            {
                **entry,
                "removal_rate": removal_rate,
            }
        )

    text_coverage = {
        name: _summarize_text_column(filtered, name)
        for name in config.features.text
        if name in filtered.columns
    }
    categorical_coverage = {
        name: _summarize_categorical_column(filtered, name)
        for name in config.features.categorical
        if name in filtered.columns
    }
    numeric_coverage = {
        name: _summarize_numeric_column(filtered, name)
        for name in config.features.numeric
        if name in filtered.columns
    }
    token_columns = [f"text_{name}_tokens" for name in config.features.text]
    token_coverage = {
        name: _summarize_text_column(features, name)
        for name in token_columns
        if name in features.columns
    }

    duplicates = (
        raw_games.select(pl.col("BGGId").is_duplicated().sum()).to_series().item()
        if "BGGId" in raw_games.columns
        else 0
    )

    rows_removed = raw_games.height - filtered.height
    removal_rate = rows_removed / raw_games.height if raw_games.height else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_rows": raw_games.height,
        "rows_after_filters": filtered.height,
        "rows_removed": rows_removed,
        "removal_rate": removal_rate,
        "filters": filters_with_rates,
        "coverage": {
            "text": text_coverage,
            "text_tokens": token_coverage,
            "categorical": categorical_coverage,
            "numeric": numeric_coverage,
        },
        "integrity": {"duplicate_bgg_ids": duplicates},
    }


def _assemble_feature_table(
    *,
    frame: pl.DataFrame,
    config: PreprocessingConfig,
    stopwords: set[str],
    synonyms: dict[str, list[str]] | None,
) -> pl.DataFrame:
    token_config = config.tokenization
    normalizer = _SynonymNormalizer(token_config, synonyms)
    text_columns = _materialize_text_columns(frame, config.features.text)
    categorical_columns = _materialize_categorical_columns(frame, config.features.categorical)
    # Keep original text columns (e.g., description) intact; emit tokenized text into
    # separate text_*_tokens columns only.
    numeric_columns = config.features.numeric
    base_columns = [
        column
        for column in (
            "bgg_id",
            "name",
            "description",
            "avg_rating",
            "num_user_ratings",
            "year_published",
            "min_players",
            "max_players",
            "playing_time_minutes",
            "complexity",
            "age_recommendation",
        )
        if column in frame.columns
    ]

    tokenizer = partial(
        _tokenize_value,
        stopwords=stopwords,
        token_config=token_config,
        normalizer=normalizer,
    )
    text_exprs = [
        pl.col(source).fill_null("").map_elements(tokenizer, return_dtype=pl.String).alias(column)
        for source, column in text_columns.items()
    ]

    categorical_exprs = [
        pl.col(source)
        .fill_null("")
        .map_elements(_format_categorical_value, return_dtype=pl.String)
        .alias(column)
        for source, column in categorical_columns.items()
    ]

    numeric_exprs = _numeric_expressions(frame, numeric_columns)
    working = frame.with_columns([*text_exprs, *categorical_exprs, *numeric_exprs])

    native_text_columns = [column for column in text_columns if column in working.columns]
    native_categorical_columns = [
        column for column in config.features.categorical if column in working.columns
    ]
    derived_columns = [
        *text_columns.values(),
        *categorical_columns.values(),
        *[f"num_{name}" for name in numeric_columns],
    ]
    columns_to_select: list[str] = []
    for column in [
        *base_columns,
        *native_text_columns,
        *native_categorical_columns,
        *derived_columns,
    ]:
        if column in working.columns and column not in columns_to_select:
            columns_to_select.append(column)
    return working.select(columns_to_select)


def _materialize_text_columns(frame: pl.DataFrame, names: Iterable[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in names:
        if name not in frame.columns:
            raise ValueError(f"Missing text column '{name}' in preprocessed dataset")
        mapping[name] = f"text_{name}_tokens"
    return mapping


def _materialize_categorical_columns(frame: pl.DataFrame, names: Iterable[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in names:
        if name not in frame.columns:
            raise ValueError(f"Missing categorical column '{name}' in preprocessed dataset")
        mapping[name] = f"cat_{name}"
    return mapping


def _summarize_text_column(frame: pl.DataFrame, column: str) -> dict[str, float]:
    if frame.is_empty():
        return {
            "non_empty": 0,
            "coverage": 0.0,
            "avg_length": 0.0,
            "p95_length": 0.0,
        }
    lengths_series = frame.select(
        pl.col(column).cast(pl.Utf8).fill_null("").str.strip_chars().str.len_chars().alias("length")
    ).to_series()
    non_empty = int((lengths_series > 0).sum())
    mean_val = lengths_series.mean()
    quantile_val = lengths_series.quantile(0.95, interpolation="higher")
    avg_length = float(mean_val) if isinstance(mean_val, (int, float)) else 0.0
    p95_length = float(quantile_val) if isinstance(quantile_val, (int, float)) else 0.0
    return {
        "non_empty": non_empty,
        "coverage": non_empty / frame.height if frame.height else 0.0,
        "avg_length": avg_length,
        "p95_length": p95_length,
    }


def _summarize_categorical_column(frame: pl.DataFrame, column: str) -> dict[str, float]:
    if frame.is_empty():
        return {"non_empty": 0, "coverage": 0.0, "distinct": 0}
    values = frame.select(
        pl.col(column).cast(pl.Utf8).fill_null("").str.strip_chars().alias("value")
    ).to_series()
    non_empty = int((values.str.len_chars() > 0).sum())
    distinct = int(values.filter(values.str.len_chars() > 0).n_unique())
    return {
        "non_empty": non_empty,
        "coverage": non_empty / frame.height if frame.height else 0.0,
        "distinct": distinct,
    }


def _numeric_expressions(
    frame: pl.DataFrame,
    numeric_columns: Iterable[str],
) -> list[pl.Expr]:
    expressions: list[pl.Expr] = []
    for name in numeric_columns:
        if name not in frame.columns:
            raise ValueError(f"Missing numeric column '{name}' in preprocessed dataset")
        stats = frame.select(
            pl.col(name).median().alias("median"),
            pl.col(name).std(ddof=0).alias("std"),
        ).row(0)
        median, std = stats
        center = float(median) if median is not None and not math.isnan(float(median)) else 0.0
        scale = float(std) if std not in (None, 0.0) and not math.isnan(float(std)) else 1.0
        expressions.append(
            ((pl.col(name).cast(pl.Float64).fill_null(center) - center) / scale).alias(
                f"num_{name}"
            )
        )
    return expressions


def _summarize_numeric_column(frame: pl.DataFrame, column: str) -> dict[str, float]:
    if frame.is_empty():
        return {
            "non_null": 0,
            "coverage": 0.0,
            "min": 0.0,
            "max": 0.0,
            "median": 0.0,
        }
    stats = frame.select(
        pl.col(column).is_not_null().sum().alias("non_null"),
        pl.col(column).min().alias("min"),
        pl.col(column).max().alias("max"),
        pl.col(column).median().alias("median"),
    ).row(0)
    non_null, minimum, maximum, median = stats
    non_null = int(non_null or 0)
    return {
        "non_null": non_null,
        "coverage": non_null / frame.height if frame.height else 0.0,
        "min": float(minimum or 0.0),
        "max": float(maximum or 0.0),
        "median": float(median or 0.0),
    }


def _tokenize_value(
    value: Any,
    *,
    stopwords: set[str],
    token_config: TokenizationConfig,
    normalizer: _SynonymNormalizer,
) -> str:
    return _tokenize_text(
        str(value),
        token_config=token_config,
        stopwords=stopwords,
        normalizer=normalizer,
    )


def _format_categorical_value(value: Any) -> str:
    return _format_categorical_text(str(value))


def _tokenize_text(
    value: str,
    *,
    token_config: TokenizationConfig,
    stopwords: set[str],
    normalizer: _SynonymNormalizer,
) -> str:
    text = value.lower()
    text = text.replace("-", " ").replace("/", " ")
    text = normalizer.normalize(text)
    tokens = _TOKEN_PATTERN.findall(text)
    if token_config.remove_common_domain_words:
        tokens = [token for token in tokens if token not in stopwords]
    if not tokens:
        return ""
    min_n, max_n = token_config.ngram_range
    ngrams: list[str] = []
    min_n = max(1, min_n)
    max_n = max(min_n, max_n)
    if min_n == 1:
        ngrams.extend(tokens)
    for size in range(max(2, min_n), max_n + 1):
        ngrams.extend(
            " ".join(tokens[index : index + size]) for index in range(0, len(tokens) - size + 1)
        )
    # Capture distinctive mechanics phrases so embeddings stay interpretable.
    return " ".join(ngrams)


def _format_categorical_text(value: str) -> str:
    tokens = _TOKEN_PATTERN.findall(value.lower())
    if not tokens:
        return ""
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return " ".join(ordered)
