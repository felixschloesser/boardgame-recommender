from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import polars as pl

from boardgame_recommender.config import (
    DomainFilterConfig,
    PreprocessingConfig,
    TokenizationConfig,
)

logger = logging.getLogger(__name__)

_SCALED_SUFFIX = "_scaled"
_TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


COLUMN_RENAMING = {
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


def preprocess_data(
    directory: Path,
    english_stopwords: set[str],
    domain_stopwords: set[str],
    config: PreprocessingConfig,
) -> tuple[pl.DataFrame, dict[str, Any]]:
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

    # DROP unused columns

    # TODO: implement preprocessing steps
    return frame, quality_report
