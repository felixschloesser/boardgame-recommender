import logging
import math
from pathlib import Path
from typing import Iterable, Sequence, cast

import polars as pl

from boardgame_recommender.config import Config

logger = logging.getLogger(__name__)

_SCALED_SUFFIX = "_scaled"


def normalized_numeric_column(name: str) -> str:
    """Return the standardized feature column name for a numeric input column."""

    return f"{name}{_SCALED_SUFFIX}"


def normalized_numeric_columns(names: list[str]) -> list[str]:
    """Return standardized column names for each numeric feature entry."""

    return [normalized_numeric_column(name) for name in names]


def _load_one_hot_tags(
    raw_data_directory: Path, file_name: str, column_name: str
) -> pl.DataFrame | None:
    """Load and melt legacy one-hot tag exports into comma separated strings."""

    file_path = raw_data_directory / file_name
    if not file_path.exists():
        return None

    tag_frame = pl.read_csv(file_path)
    tag_columns = [column for column in tag_frame.columns if column != "BGGId"]
    if not tag_columns:
        return None

    melted_frame = tag_frame.unpivot(
        index=["BGGId"],
        on=tag_columns,
        variable_name="tag",
        value_name="value",
    )
    tag_strings = (
        melted_frame.filter(pl.col("value") == 1)
        .group_by("BGGId")
        .agg(pl.col("tag").sort().str.join(", "))
        .rename({"BGGId": "bgg_id", "tag": column_name})
    )
    return tag_strings


def _combine_text(
    column_names: Iterable[str], target_alias: str, separator: str = " "
) -> pl.Expr:
    """Concatenate nullable text columns into a single feature column."""

    expressions = [pl.col(column_name).fill_null("") for column_name in column_names]
    if not expressions:
        return pl.lit("").alias(target_alias)
    return (
        pl.concat_str(expressions, separator=separator)
        .str.replace(r"\s+", " ")
        .str.strip_chars()
        .replace("", None)
        .alias(target_alias)
    )


def _format_tag_tokens(tag_value: str | None, prefix: str) -> str | None:
    """Normalize comma separated mechanic/category/theme tags to tokens."""

    if not tag_value:
        return None
    tokens = [token.strip() for token in tag_value.split(",") if token.strip()]
    if not tokens:
        return None
    normalized_tokens = [
        f"{prefix}::{token.lower().replace(' ', '_')}" for token in tokens
    ]
    return " ".join(normalized_tokens)


def _tag_text_column(column_name: str, prefix: str, alias: str) -> pl.Expr:
    """Project multi-valued tag strings into prefixed tf-idf word buckets."""

    return (
        pl.col(column_name)
        .map_elements(lambda value: _format_tag_tokens(value, prefix))
        .alias(alias)
    )


def _append_normalized_numeric_features(
    data_frame: pl.DataFrame, column_names: Sequence[str]
) -> pl.DataFrame:
    """Append z-scored numeric columns used later during training."""

    expressions: list[pl.Expr] = []
    for column_name in column_names:
        if column_name not in data_frame.columns:
            raise ValueError(
                f"Missing numeric column '{column_name}' needed for normalization"
            )
        column_series = data_frame[column_name].cast(pl.Float64)
        mean_value = cast(float | None, column_series.mean())
        standard_deviation = cast(float | None, column_series.std())
        target_name = normalized_numeric_column(column_name)

        if mean_value is None or math.isnan(mean_value):
            mean_value = 0.0
        if (
            standard_deviation is None
            or standard_deviation == 0
            or math.isnan(standard_deviation)
        ):
            expressions.append(pl.lit(0.0).alias(target_name))
            continue

        expressions.append(
            (
                (
                    pl.col(column_name).cast(pl.Float64).fill_null(mean_value)
                    - mean_value
                )
                / standard_deviation
            ).alias(target_name)
        )

    if expressions:
        data_frame = data_frame.with_columns(expressions)
    return data_frame


def _extract_categories_from_flags(
    data_frame: pl.DataFrame,
) -> tuple[pl.DataFrame | None, list[str]]:
    """Convert legacy Cat:* indicator columns into sorted category strings."""

    category_columns = [
        column_name for column_name in data_frame.columns if column_name.startswith("Cat:")
    ]
    if not category_columns:
        return None, []

    category_subset = data_frame.select(["bgg_id", *category_columns])
    melted_frame = category_subset.unpivot(
        index="bgg_id",
        on=category_columns,
        variable_name="category",
        value_name="value",
    )
    categories_frame = (
        melted_frame.filter(pl.col("value") > 0)
        .with_columns(pl.col("category").str.replace("Cat:", ""))
        .group_by("bgg_id")
        .agg(pl.col("category").sort().str.join(", "))
        .rename({"category": "categories_base"})
    )
    return categories_frame, category_columns


def preprocess_data(
    configuration: Config,
    raw_data_directory_override: Path | None = None,
    output_path_override: Path | None = None,
    top_record_limit: int | None = None,
) -> Path:
    """Clean raw CSV exports and emit a feature store parquet file."""

    effective_top_record_limit = (
        top_record_limit
        if top_record_limit is not None
        else configuration.preprocessing.top_record_limit
    )

    raw_data_directory = (
        Path(raw_data_directory_override)
        if raw_data_directory_override
        else configuration.paths.raw_data
    )
    output_path = (
        Path(output_path_override)
        if output_path_override
        else configuration.paths.processed_features
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Preprocessing boardgame data from %s -> %s (top_record_limit=%s)",
        raw_data_directory,
        output_path,
        effective_top_record_limit,
    )

    games_frame = pl.read_csv(raw_data_directory / "games.csv")
    logger.info(
        "Loaded %d raw titles; renaming columns to normalized schema",
        games_frame.height,
    )
    games_frame = games_frame.rename(
        {
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
    )

    category_flags_frame, category_flag_columns = _extract_categories_from_flags(
        games_frame
    )
    if category_flag_columns:
        games_frame = games_frame.drop(category_flag_columns)

    mechanics_tags_frame = _load_one_hot_tags(
        raw_data_directory, "mechanics.csv", "mechanics"
    )
    subcategory_tags_frame = _load_one_hot_tags(
        raw_data_directory, "subcategories.csv", "subcategories"
    )
    theme_tags_frame = _load_one_hot_tags(raw_data_directory, "themes.csv", "themes")

    enriched_frame = games_frame
    logger.info("Enriching games with category/mechanic/theme tag tables")
    if category_flags_frame is not None:
        enriched_frame = enriched_frame.join(
            category_flags_frame, on="bgg_id", how="left"
        )
    if mechanics_tags_frame is not None:
        enriched_frame = enriched_frame.join(
            mechanics_tags_frame, on="bgg_id", how="left"
        )
    if subcategory_tags_frame is not None:
        enriched_frame = enriched_frame.join(
            subcategory_tags_frame, on="bgg_id", how="left"
        )
    if theme_tags_frame is not None:
        enriched_frame = enriched_frame.join(
            theme_tags_frame, on="bgg_id", how="left"
        )

    logger.info(
        "Deriving playing time and ensuring mechanics column exists for downstream joins"
    )
    enriched_frame = enriched_frame.with_columns(
        [
            pl.coalesce(pl.col("community_playtime"), pl.col("mfg_playtime")).alias(
                "playing_time_minutes"
            ),
            pl.col("mechanics").alias("mechanics"),
        ]
    )

    category_source_columns = [
        column_name
        for column_name in ("categories_base", "subcategories")
        if column_name in enriched_frame.columns
    ]
    if category_source_columns:
        enriched_frame = enriched_frame.with_columns(
            _combine_text(category_source_columns, target_alias="categories")
        )
    else:
        enriched_frame = enriched_frame.with_columns(pl.lit(None).alias("categories"))
    if "categories_base" in enriched_frame.columns:
        enriched_frame = enriched_frame.drop("categories_base")

    for optional_column in ("mechanics", "subcategories", "themes", "categories"):
        if optional_column not in enriched_frame.columns:
            enriched_frame = enriched_frame.with_columns(
                pl.lit(None).alias(optional_column)
            )

    textual_feature_columns = ["description", "mechanics", "categories"]
    logger.info("Building composite text blob from %s", textual_feature_columns)
    enriched_frame = enriched_frame.with_columns(
        _combine_text(
            textual_feature_columns, target_alias="text_blob", separator=" "
        ),
    )

    tag_column_mapping = {
        "mechanics": ("mechanic", "mechanics_tags"),
        "categories": ("category", "categories_tags"),
        "themes": ("theme", "themes_tags"),
    }
    logger.info(
        "Projecting mechanics/categories/themes into token-tag columns for TF-IDF"
    )
    enriched_frame = enriched_frame.with_columns(
        [
            _tag_text_column(column, prefix, alias)
            for column, (prefix, alias) in tag_column_mapping.items()
        ]
    )

    required_columns = {
        "bgg_id",
        "name",
        "description",
        "mechanics",
        "categories",
        "mechanics_tags",
        "categories_tags",
        "themes_tags",
        "text_blob",
        "avg_rating",
        "min_players",
        "max_players",
        "playing_time_minutes",
        "year_published",
        "num_user_ratings",
        "complexity",
    }
    missing_columns = required_columns.difference(set(enriched_frame.columns))
    if missing_columns:
        raise ValueError(f"Missing expected columns: {sorted(missing_columns)}")

    if effective_top_record_limit is not None:
        logger.info(
            "Restricting dataset to the top %d titles by number of user ratings",
            effective_top_record_limit,
        )
        enriched_frame = enriched_frame.sort(
            "num_user_ratings", descending=True
        ).head(effective_top_record_limit)

    if configuration.features.numeric_columns:
        logger.info(
            "Standardizing numeric features %s before model training",
            configuration.features.numeric_columns,
        )
        enriched_frame = _append_normalized_numeric_features(
            enriched_frame, configuration.features.numeric_columns
        )

    if logger.isEnabledFor(logging.DEBUG):
        sample_rows = enriched_frame.head(5)
        logger.debug(
            "Processed sample (first %d rows) to sanity-check feature shapes:\n%s",
            sample_rows.height,
            sample_rows,
        )

    enriched_frame.write_parquet(output_path)
    logger.info(
        "Finished preprocessing -> %s (rows=%d, columns=%d)",
        output_path,
        enriched_frame.height,
        len(enriched_frame.columns),
    )
    return output_path
