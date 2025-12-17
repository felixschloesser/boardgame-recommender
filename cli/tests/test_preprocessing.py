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
        "NumOwned": [1000, 2000],
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
    assert "description" in features.columns
    assert "text_description_tokens" in features.columns
    assert "mechanics" in features.columns
    assert "cat_mechanics" in features.columns
    assert "num_avg_rating" in features.columns

    assert features["description"][0] == "Fast co-op adventure game"

    first_description = features["text_description_tokens"][0]
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


def test_popularity_override_keeps_low_rated_hits(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    games = {
        "BGGId": [1, 2, 3, 4],
        "Name": ["Classic", "Cult Classic", "Obscure", "Modern Gem"],
        "Description": ["", "", "", ""],
        "YearPublished": [1950, 1990, 2005, 2021],
        "AvgRating": [4.0, 4.3, 4.1, 7.2],
        "MinPlayers": [2, 2, 2, 1],
        "MaxPlayers": [6, 4, 4, 4],
        "ComMaxPlaytime": [90, 60, 45, 60],
        "ComMinPlaytime": [60, 45, 30, 45],
        "MfgPlaytime": [120, 60, 60, 60],
        "NumUserRatings": [20000, 500, 500, 1200],
        "GameWeight": [1.5, 2.0, 2.0, 2.5],
        "ComAgeRec": [8, 10, 12, 10],
        "NumOwned": [50000, 60000, 50, 5000],
    }
    mechanics = {
        "BGGId": [1, 2, 3, 4],
        "Roll": [1, 0, 0, 0],
        "Trade": [0, 1, 0, 0],
        "Bluff": [0, 0, 1, 0],
        "Co-op": [0, 0, 0, 1],
    }
    subcategories = {
        "BGGId": [1, 2, 3, 4],
        "Family": [1, 1, 0, 0],
        "Card": [0, 0, 1, 0],
        "Strategy": [0, 0, 0, 1],
    }
    themes = {
        "BGGId": [1, 2, 3, 4],
        "Classic": [1, 1, 0, 0],
        "Niche": [0, 0, 1, 0],
        "Modern": [0, 0, 0, 1],
    }

    _write_csv(raw_dir / "games.csv", games)
    _write_csv(raw_dir / "mechanics.csv", mechanics)
    _write_csv(raw_dir / "subcategories.csv", subcategories)
    _write_csv(raw_dir / "themes.csv", themes)

    config = _basic_preprocessing_config()
    config.filters.min_avg_rating = 6.0
    config.filters.popularity_override_min_num_ratings = 10000
    config.filters.popularity_override_top_owned_quantile = 0.5
    config.filters.min_popularity_quantile = 0.0

    features, report = preprocess_data(
        directory=raw_dir,
        stopwords=set(),
        config=config,
        synonyms=None,
    )

    assert set(features["name"].to_list()) == {
        "Classic",
        "Cult Classic",
        "Modern Gem",
    }

    report_by_name = {entry["name"]: entry for entry in report["filters"]}
    override = report_by_name["min_avg_rating"]["popularity_override"]
    assert override["kept_by_override"] == 2
    assert override["min_num_user_ratings"] == 10000
