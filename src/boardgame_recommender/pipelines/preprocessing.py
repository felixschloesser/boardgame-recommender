from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Iterable

import polars as pl

from boardgame_recommender.config import (
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
    def __init__(
        self, config: TokenizationConfig, synonyms: dict[str, list[str]] | None
    ) -> None:
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
                pattern = re.compile(rf"\\b{re.escape(self._canonicalize(variant))}\\b")
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
) -> tuple[pl.DataFrame, dict[str, Any]]:
    directory = directory.resolve()
    logger.info("Loading raw files from %s", directory)
    stopword_lookup = {word.lower() for word in stopwords}

    games = _load_games(directory)
    categories = _extract_category_flags(games)
    mechanics = _load_tag_table(directory / "mechanics.csv", "mechanics")
    subcategories = _load_tag_table(directory / "subcategories.csv", "subcategories")
    themes = _load_tag_table(directory / "themes.csv", "themes")

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

    filtered, filters_report = _apply_filters(enriched, config.filters)
    features = _assemble_feature_table(
        frame=filtered,
        config=config,
        stopwords=stopword_lookup,
        synonyms=synonyms,
    )

    quality_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_rows": games.height,
        "rows_after_filters": filtered.height,
        "filters": filters_report,
    }
    return features, quality_report


def _read_csv(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required dataset '{path.name}' not found at {path}.")
    return pl.read_csv(path)


def _load_games(directory: Path) -> pl.DataFrame:
    games = _read_csv(directory / "games.csv")
    missing = [column for column in _COLUMN_RENAMING if column not in games.columns]
    if missing:
        raise ValueError(
            "games.csv missing required columns: " + ", ".join(sorted(missing))
        )
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
        return pl.DataFrame({"bgg_id": [], "categories": []})
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
            pl.col("year_published").is_null()
            | (pl.col("year_published") <= filters.max_year)
        )
        report.append(
            {
                "name": "max_year",
                "value": filters.max_year,
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
                "removed": before - current.height,
            }
        )

    if filters.min_avg_rating:
        before = current.height
        current = current.filter(pl.col("avg_rating") >= filters.min_avg_rating)
        report.append(
            {
                "name": "min_avg_rating",
                "value": filters.min_avg_rating,
                "removed": before - current.height,
            }
        )

    before = current.height
    current = current.filter(
        pl.col("min_players").is_null()
        | (pl.col("min_players") <= filters.max_required_players)
    )
    report.append(
        {
            "name": "max_required_players",
            "value": filters.max_required_players,
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
            "removed": before - current.height,
        }
    )
    return current, report


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
    categorical_columns = _materialize_categorical_columns(
        frame, config.features.categorical
    )
    numeric_columns = config.features.numeric
    base_columns = [
        column
        for column in (
            "bgg_id",
            "name",
            "avg_rating",
            "min_players",
            "max_players",
            "playing_time_minutes",
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
        pl.col(source)
        .fill_null("")
        .map_elements(tokenizer, return_dtype=pl.String)
        .alias(column)
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

    derived_columns = [
        *text_columns.values(),
        *categorical_columns.values(),
        *[f"num_{name}" for name in numeric_columns],
    ]
    columns_to_select = [column for column in base_columns if column in working.columns]
    columns_to_select.extend(
        [column for column in derived_columns if column in working.columns]
    )
    return working.select(columns_to_select)


def _materialize_text_columns(
    frame: pl.DataFrame, names: Iterable[str]
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in names:
        if name not in frame.columns:
            raise ValueError(f"Missing text column '{name}' in preprocessed dataset")
        mapping[name] = f"text_{name}"
    return mapping


def _materialize_categorical_columns(
    frame: pl.DataFrame, names: Iterable[str]
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in names:
        if name not in frame.columns:
            raise ValueError(
                f"Missing categorical column '{name}' in preprocessed dataset"
            )
        mapping[name] = f"cat_{name}"
    return mapping


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
        center = (
            float(median)
            if median is not None and not math.isnan(float(median))
            else 0.0
        )
        scale = (
            float(std) if std not in (None, 0.0) and not math.isnan(float(std)) else 1.0
        )
        expressions.append(
            ((pl.col(name).cast(pl.Float64).fill_null(center) - center) / scale).alias(
                f"num_{name}"
            )
        )
    return expressions


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
            " ".join(tokens[index : index + size])
            for index in range(0, len(tokens) - size + 1)
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
