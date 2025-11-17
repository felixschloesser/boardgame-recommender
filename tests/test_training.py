from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from boardgame_recommender.pipelines.training import train


def test_train_empty_input_raises(config):
    empty = pl.DataFrame()
    with pytest.raises(ValueError, match="empty feature table"):
        train(features=empty, config=config)


def test_train_requires_feature_columns(config):
    frame = pl.DataFrame(
        {
            "bgg_id": [1],
            "name": ["Alpha"],
            "avg_rating": [7.0],
        }
    )
    with pytest.raises(ValueError, match="No training features detected"):
        train(features=frame, config=config)


@pytest.mark.end_to_end
def test_feature_schema_detection(sample_features, config):
    embedding = train(features=sample_features, config=config)
    schema = embedding.metadata["feature_schema"]
    assert set(schema["text"]) == {"text_description"}
    assert set(schema["categorical"]) == {"cat_mechanics"}
    assert set(schema["numeric"]) == {
        "num_avg_rating",
        "num_min_players",
        "num_max_players",
        "num_complexity",
    }


@pytest.mark.end_to_end
def test_normalization_applied_when_enabled(sample_features, config):
    cfg = config.model_copy(deep=True)
    cfg.training.taste_model.normalize_taste_vectors = True

    embedding = train(features=sample_features, config=cfg)
    taste_columns = embedding.metadata["embedding_columns"]
    taste_matrix = embedding.vectors.select(taste_columns).to_numpy()
    norms = np.linalg.norm(taste_matrix, axis=1)
    assert np.all(
        np.isclose(norms, 1.0) | np.isclose(norms, 0.0)
    ), "All taste rows should be normalized."


@pytest.mark.end_to_end
def test_taste_dimension_shape_and_metadata(sample_features, config):
    cfg = config.model_copy(deep=True)
    cfg.training.taste_model.taste_dimensions = 3

    embedding = train(features=sample_features, config=cfg)
    taste_columns = [f"taste_{index}" for index in range(3)]

    assert embedding.metadata["embedding_columns"] == taste_columns
    for column in taste_columns:
        assert column in embedding.vectors.columns


def test_train_rejects_non_positive_taste_dimensions(sample_features, config):
    cfg = config.model_copy(deep=True)
    cfg.training.taste_model.taste_dimensions = 0
    with pytest.raises(ValueError, match="taste_dimensions must be greater than zero"):
        train(features=sample_features, config=cfg)
