from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Iterable, Sequence

import polars as pl

from boardgame_recommender.config import PreprocessingConfig, TokenizationConfig

logger = logging.getLogger(__name__)

_SCALED_SUFFIX = "_scaled"
_TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


def normalized_numeric_column(name: str) -> str:
    """Return the normalized column suffix used throughout the pipeline."""

    return f"{name}{_SCALED_SUFFIX}"


def normalized_numeric_columns(names: Sequence[str]) -> list[str]:
    """Return normalized column names for the provided numeric sources."""

    return [normalized_numeric_column(name) for name in names]


def _read_csv(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Cannot find required dataset '{path.name}' at {path}, \
            make sure you download the BoardGameGeek exports from keggle first."
        )
    return pl.read_csv(path)


def _load_games(directory: Path) -> pl.DataFrame:
    games = _read_csv(directory / "games.csv")
    rename_map = {
        "BGGId": "bgg_id",
        "Name": "name",
        "Description": "description",
        "YearPublished": "year_published",
        "AvgRating": "avg_rating",
        "MinPlayers": "min_players",
        "MaxPlayers": "max_players",
        "ComMaxPlaytime": "community_playtime",
        "MfgPlaytime": "mfg_playtime",
        "NumUserRatings": "num_user_ratings",
        "GameWeight": "complexity",
    }
    missing_columns = [source for source in rename_map if source not in games.columns]
    if missing_columns:
        raise ValueError(
            f"games.csv is missing required columns: {', '.join(sorted(missing_columns))}"
        )
    return games.rename(rename_map)


def _extract_category_flags(frame: pl.DataFrame) -> pl.DataFrame:
    category_columns = [
        column_name for column_name in frame.columns if column_name.startswith("Cat:")
    ]
    if not category_columns:
        return pl.DataFrame(
            {"bgg_id": pl.Series([], dtype=pl.Int64), "categories_base": []}
        )

    melted = frame.select(["bgg_id", *category_columns]).unpivot(
        index="bgg_id",
        on=category_columns,
        variable_name="category",
        value_name="value",
    )
    categories = (
        melted.filter(pl.col("value") > 0)
        .with_columns(pl.col("category").str.replace("Cat:", ""))
        .group_by("bgg_id")
        .agg(pl.col("category").sort().str.join(", "))
        .rename({"category": "categories_base"})
    )
    return categories


def _load_tag_table(directory: Path, filename: str, alias: str) -> pl.DataFrame:
    path = directory / filename
    if not path.exists():
        return pl.DataFrame({"bgg_id": pl.Series([], dtype=pl.Int64), alias: []})
    table = pl.read_csv(path)
    non_bgg_columns = [column for column in table.columns if column != "BGGId"]
    if not non_bgg_columns:
        return pl.DataFrame({"bgg_id": pl.Series([], dtype=pl.Int64), alias: []})
    melted = table.unpivot(
        index=["BGGId"],
        on=non_bgg_columns,
        variable_name="value",
        value_name="flag",
    )
    gathered = (
        melted.filter(pl.col("flag") == 1)
        .group_by("BGGId")
        .agg(pl.col("value").sort().str.join(", "))
        .rename({"BGGId": "bgg_id", "value": alias})
    )
    return gathered


def _prepare_stopwords(
    english_stopwords: set[str],
    domain_stopwords: set[str],
    token_config: TokenizationConfig,
) -> set[str]:
    def _normalize(values: set[str]) -> set[str]:
        return {token.lower() for token in values}

    english = _normalize(english_stopwords)
    domain = _normalize(domain_stopwords)
    combined = english | domain

    active: set[str] = set()
    if token_config.remove_english_stopwords:
        active |= english
    if token_config.remove_domain_stopwords:
        active |= domain
    if not active:
        active = combined

    allowed = {token.lower() for token in token_config.allowed_stopwords}
    return {token for token in active if token not in allowed}


def _normalize_free_text(
    value: str | None, stopwords: set[str], deduplicate: bool
) -> str | None:
    if not value:
        return None
    tokens = _TOKEN_PATTERN.findall(value.lower())
    filtered_tokens = [token for token in tokens if token not in stopwords]
    if deduplicate:
        seen: set[str] = set()
        filtered_tokens = [
            token for token in filtered_tokens if not (token in seen or seen.add(token))
        ]
    return " ".join(filtered_tokens) if filtered_tokens else None


def _normalize_tag_text(value: str | None, prefix: str) -> str | None:
    if not value:
        return None
    tokens = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        normalized = token.lower().replace(" ", "_")
        tokens.append(f"{prefix}::{normalized}")
    return " ".join(sorted(set(tokens))) if tokens else None


def _scale_numeric_series(series: pl.Series, strategy: str) -> pl.Expr:
    column = series.cast(pl.Float64)
    alias = normalized_numeric_column(series.name)

    if strategy == "zscore":
        mean = column.mean()
        std = column.std()
        if std is None or std == 0 or math.isnan(std):
            return pl.lit(0.0).alias(alias)
        return ((pl.col(series.name).cast(pl.Float64) - (mean or 0.0)) / std).alias(
            alias
        )

    if strategy == "min-max":
        min_value = column.min()
        max_value = column.max()
        if min_value is None or max_value is None or min_value == max_value:
            return pl.lit(0.0).alias(alias)
        return (
            (pl.col(series.name).cast(pl.Float64) - min_value) / (max_value - min_value)
        ).alias(alias)

    if strategy == "robust":
        q1 = column.quantile(0.25, interpolation="midpoint")
        q3 = column.quantile(0.75, interpolation="midpoint")
        if q1 is None or q3 is None or q1 == q3:
            return pl.lit(0.0).alias(alias)
        return ((pl.col(series.name).cast(pl.Float64) - q1) / (q3 - q1)).alias(alias)

    raise ValueError(f"Unsupported normalization strategy: {strategy}")


def _append_numeric_features(
    frame: pl.DataFrame, config: PreprocessingConfig
) -> pl.DataFrame:
    numeric_config = config.features.numeric
    expressions: list[pl.Expr] = []

    normal_columns = numeric_config.normal.columns
    heavy_tailed_columns = numeric_config.heavy_tail.columns

    for column in normal_columns:
        if column not in frame.columns:
            logger.warning("Numeric column '%s' missing; filling with zeros", column)
            frame = frame.with_columns(pl.lit(0.0).alias(column))
        expressions.append(
            _scale_numeric_series(
                frame[column], numeric_config.normal.normalization_strategy
            )
        )

    for column in heavy_tailed_columns:
        if column not in frame.columns:
            logger.warning("Numeric column '%s' missing; filling with zeros", column)
            frame = frame.with_columns(pl.lit(0.0).alias(column))
        expressions.append(
            _scale_numeric_series(
                frame[column], numeric_config.heavy_tail.normalization_strategy
            )
        )

    if expressions:
        frame = frame.with_columns(expressions)
    return frame


def _apply_cutoff(frame: pl.DataFrame, config: PreprocessingConfig) -> pl.DataFrame:
    metric = config.cutoff_metric
    if metric not in frame.columns:
        raise ValueError(f"Cutoff metric '{metric}' not present in dataset")
    quantile = config.cutoff_quantile
    if quantile <= 0:
        return frame
    threshold_frame = frame.select(
        pl.col(metric).quantile(quantile, interpolation="higher").alias("threshold")
    )
    threshold = threshold_frame["threshold"][0]
    if threshold is None:
        return frame
    return frame.filter(pl.col(metric) >= threshold)


def _clean_textual_columns(
    frame: pl.DataFrame, stopwords: set[str], config: PreprocessingConfig
) -> pl.DataFrame:
    token_config = config.tokenization

    def _clean_text(value: str | None) -> str | None:
        return _normalize_free_text(
            value, stopwords, token_config.vocabulary_deduplication
        )

    text_columns = config.features.text.columns
    for column in text_columns:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None).alias(column))
    frame = frame.with_columns(
        [
            pl.col(column).cast(pl.Utf8).map_elements(_clean_text).alias(column)
            for column in text_columns
        ]
    )

    categorical_columns = config.features.categorical.columns
    for column in categorical_columns:
        if column not in frame.columns:
            frame = frame.with_columns(pl.lit(None).alias(column))
    category_aliases = {
        "mechanics": "mechanic",
        "categories": "category",
        "themes": "theme",
    }
    frame = frame.with_columns(
        [
            pl.col(column)
            .cast(pl.Utf8)
            .map_elements(
                lambda value, prefix=category_aliases.get(
                    column, column
                ): _normalize_tag_text(value, prefix)
            )
            .alias(column)
            for column in categorical_columns
        ]
    )
    return frame


def preprocess_data(
    directory: Path,
    english_stopwords: set[str],
    domain_stopwords: set[str],
    config: PreprocessingConfig,
) -> pl.DataFrame:
    """
    Transform the raw BoardGameGeek exports into a clean feature table ready for training.
    """

    directory = directory.resolve()
    logger.info("Loading raw data from %s", directory)
    games = _load_games(directory)

    categories = _extract_category_flags(games)
    mechanics = _load_tag_table(directory, "mechanics.csv", "mechanics")
    subcategories = _load_tag_table(directory, "subcategories.csv", "subcategories")
    themes = _load_tag_table(directory, "themes.csv", "themes")

    frame = games.join(categories, on="bgg_id", how="left")
    frame = frame.join(mechanics, on="bgg_id", how="left")
    frame = frame.join(subcategories, on="bgg_id", how="left")
    frame = frame.join(themes, on="bgg_id", how="left")

    frame = frame.with_columns(
        pl.coalesce(pl.col("community_playtime"), pl.col("mfg_playtime")).alias(
            "playing_time_minutes"
        )
    )

    if "categories_base" in frame.columns:
        if "categories" not in frame.columns:
            frame = frame.with_columns(pl.lit(None).alias("categories"))
        frame = frame.with_columns(
            pl.when(pl.col("categories").is_null())
            .then(pl.col("categories_base"))
            .otherwise(pl.col("categories"))
            .alias("categories")
        ).drop("categories_base")

    frame = _apply_cutoff(frame, config)

    final_stopwords = _prepare_stopwords(
        english_stopwords,
        domain_stopwords,
        config.tokenization,
    )
    frame = _clean_textual_columns(frame, final_stopwords, config)
    frame = _append_numeric_features(frame, config)

    essential_columns = [
        "bgg_id",
        "name",
        "avg_rating",
        "min_players",
        "max_players",
        "playing_time_minutes",
        "description",
    ]
    missing = [column for column in essential_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing essential columns after preprocessing: {missing}")

    logger.info(
        "Finished preprocessing (rows=%d, columns=%d)", frame.height, frame.width
    )
    return frame
