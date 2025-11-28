from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import polars as pl
import pytest
from boardgames_cli.config import (
    FeaturesConfig,
    FeatureWeightsConfig,
    PreprocessingConfig,
    PreprocessingFilters,
    TokenizationConfig,
)
from boardgames_cli.pipelines.preprocessing import preprocess_data


def _write_csv(path: Path, data: Mapping[str, Sequence[object]]) -> None:
    pl.DataFrame(data).write_csv(path)


def _basic_preprocessing_config() -> PreprocessingConfig:
    weights = FeatureWeightsConfig(
        description=1.0,
        mechanics=1.0,
        categories=1.0,
        themes=1.0,
        numeric=1.0,
    )
    filters = PreprocessingFilters(
        max_year=2030,
        min_popularity_quantile=0.0,
        min_avg_rating=0.0,
        max_required_players=10,
        max_playing_time_minutes=500,
    )
    features = FeaturesConfig(
        text=["description"],
        categorical=["mechanics"],
        numeric=["avg_rating"],
        weights=weights,
    )
    tokenization = TokenizationConfig(
        unify_synonyms=True,
        remove_common_domain_words=True,
        ngram_range=(1, 2),
    )
    return PreprocessingConfig(
        filters=filters,
        features=features,
        tokenization=tokenization,
    )


def test_preprocess_data_generates_feature_table(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    games = {
        "BGGId": [1, 2],
        "Name": ["Alpha", "Beta"],
        "Description": ["Fast co-op adventure game", "Deck building duel"],
        "YearPublished": [2020, 2018],
        "AvgRating": [8.0, 7.0],
        "MinPlayers": [1, 2],
        "MaxPlayers": [4, 4],
        "ComMaxPlaytime": [60, 45],
        "ComMinPlaytime": [50, 30],
        "MfgPlaytime": [70, 45],
        "NumUserRatings": [500, 400],
        "GameWeight": [2.5, 2.0],
        "ComAgeRec": [10, 8],
        "Cat: Strategy": [1, 0],
        "Cat: Family": [0, 1],
    }
    mechanics = {
        "BGGId": [1, 2],
        "Co-op": [1, 0],
        "Deck Building": [0, 1],
    }
    subcategories = {
        "BGGId": [1, 2],
        "Adventure": [1, 0],
        "Card": [0, 1],
    }
    themes = {
        "BGGId": [1, 2],
        "Fantasy": [1, 0],
        "SciFi": [0, 1],
    }

    _write_csv(raw_dir / "games.csv", games)
    _write_csv(raw_dir / "mechanics.csv", mechanics)
    _write_csv(raw_dir / "subcategories.csv", subcategories)
    _write_csv(raw_dir / "themes.csv", themes)

    config = _basic_preprocessing_config()
    stopwords = {"game"}
    synonyms = {"cooperative": ["co-op"]}

    features, report = preprocess_data(
        directory=raw_dir,
        stopwords=stopwords,
        config=config,
        synonyms=synonyms,
    )

    assert features.height == 2
    assert "text_description" in features.columns
    assert "cat_mechanics" in features.columns
    assert "num_avg_rating" in features.columns

    first_description = features["text_description"][0]
    assert "cooperative" in first_description
    assert "game" not in first_description

    report_by_name = {entry["name"]: entry for entry in report["filters"]}
    assert "max_year" in report_by_name
    assert "max_required_players" in report_by_name
    assert "max_playing_time_minutes" in report_by_name
    assert "min_popularity_quantile" not in report_by_name
    assert "min_avg_rating" not in report_by_name
    assert all(entry["removed"] == 0 for entry in report_by_name.values())


def test_preprocess_data_errors_when_games_missing(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    config = _basic_preprocessing_config()

    with pytest.raises(FileNotFoundError, match="games.csv"):
        preprocess_data(
            directory=raw_dir,
            stopwords=set(),
            config=config,
            synonyms=None,
        )
