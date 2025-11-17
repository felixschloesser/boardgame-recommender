from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from boardgame_recommender.pipelines.training import Embedding
from boardgame_recommender.recommend import (
    RecommendationContext,
    _aggregate_scores,
    _cosine_similarity,
    _determine_centroid_count,
    _run_kmeans,
    recommend_games,
)


def test_missing_liked_games_raise_with_suggestions(sample_embedding, recommendation_config):
    with pytest.raises(ValueError) as exc:
        recommend_games(
            embedding=sample_embedding,
            liked_games=["Zeta"],
            player_count=2,
            available_time_minutes=60,
            amount=5,
            config=recommendation_config,
        )
    assert "closest" in str(exc.value)


def test_candidate_pool_empty_returns_no_results(sample_embedding, recommendation_config):
    results = recommend_games(
        embedding=sample_embedding,
        liked_games=["Alpha"],
        player_count=2,
        available_time_minutes=5,
        amount=5,
        config=recommendation_config,
    )
    assert results == []


def test_recommendations_are_deterministic_given_seed(sample_embedding, recommendation_config):
    cfg = recommendation_config.model_copy(deep=True)
    cfg.taste_model.min_samples_per_centroid = 2
    cfg.taste_model.dynamic_centroids = False

    liked_games = ["Alpha", "Beta", "Gamma", "Delta"]
    kwargs = dict(
        embedding=sample_embedding,
        liked_games=liked_games,
        player_count=3,
        available_time_minutes=200,
        amount=2,
        config=cfg,
    )

    first = recommend_games(**kwargs)
    second = recommend_games(**kwargs)
    assert first == second


def test_result_formatting_converts_numeric_fields(sample_embedding, recommendation_config):
    results = recommend_games(
        embedding=sample_embedding,
        liked_games=["Alpha"],
        player_count=2,
        available_time_minutes=200,
        amount=3,
        config=recommendation_config,
    )

    assert results, "Expected at least one recommendation."

    gamma_row = next((row for row in results if row["name"] == "Gamma"), None)
    assert gamma_row is not None
    assert gamma_row["avg_rating"] == 0.0
    assert gamma_row["playing_time"] == 30
    assert isinstance(gamma_row["min_players"], int)
    assert isinstance(gamma_row["max_players"], int)


def test_similarity_aggregation_modes_affect_ranking(
    sample_embedding, recommendation_config, monkeypatch
):
    def fake_tastes(self, liked_matrix):
        return np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64)

    monkeypatch.setattr(RecommendationContext, "build_taste_vectors", fake_tastes)

    cfg_max = recommendation_config.model_copy(deep=True)
    cfg_max.similarity_aggregation = "max"
    cfg_mean = recommendation_config.model_copy(deep=True)
    cfg_mean.similarity_aggregation = "mean"

    kwargs = dict(
        embedding=sample_embedding,
        liked_games=["Alpha"],
        player_count=2,
        available_time_minutes=200,
        amount=2,
    )

    max_results = recommend_games(config=cfg_max, **kwargs)
    mean_results = recommend_games(config=cfg_mean, **kwargs)

    assert max_results[0]["name"] == "Beta"
    assert mean_results[0]["name"] == "Gamma"


def test_validate_query_rejects_invalid_inputs(recommendation_context):
    context = recommendation_context
    with pytest.raises(ValueError, match="Provide at least one liked game"):
        context.validate_query([], player_count=1, available_time_minutes=10, amount=1)
    with pytest.raises(ValueError, match="player_count must be positive"):
        context.validate_query(["Alpha"], player_count=0, available_time_minutes=10, amount=1)
    with pytest.raises(ValueError, match="available_time_minutes must be positive"):
        context.validate_query(["Alpha"], player_count=1, available_time_minutes=0, amount=1)
    with pytest.raises(ValueError, match="amount must be positive"):
        context.validate_query(["Alpha"], player_count=1, available_time_minutes=10, amount=0)


def test_aggregate_scores_rejects_unknown_strategy():
    matrix = np.array([[0.1, 0.2]])
    with pytest.raises(ValueError, match="similarity_aggregation"):
        _aggregate_scores(matrix, strategy="median")


def test_cosine_similarity_handles_empty_inputs():
    empty = np.zeros((0, 2))
    tastes = np.ones((1, 2))
    similarity = _cosine_similarity(empty, tastes)
    assert similarity.shape == (0, 1)


def test_context_rejects_missing_metadata_columns(recommendation_config):
    embedding = Embedding(
        run_identifier="broken",
        vectors=pl.DataFrame({"bgg_id": [1], "name": ["Alpha"], "taste_0": [0.1]}),
        metadata={"embedding_columns": ["taste_0", "taste_1"]},
    )
    with pytest.raises(ValueError, match="missing from vectors"):
        RecommendationContext.from_embedding(embedding, recommendation_config)


def test_context_rejects_vectors_without_taste_columns(recommendation_config):
    embedding = Embedding(
        run_identifier="missing",
        vectors=pl.DataFrame({"bgg_id": [1], "name": ["Alpha"]}),
        metadata={},
    )
    with pytest.raises(ValueError, match="do not contain any taste"):
        RecommendationContext.from_embedding(embedding, recommendation_config)


def test_locate_liked_rows_errors_when_partial_matches(recommendation_context):
    context = recommendation_context
    with pytest.raises(ValueError, match="Missing liked games"):
        context.locate_liked_rows(["Alpha", "Zeta"])


def test_determine_centroid_count_dynamic_scaling():
    result = _determine_centroid_count(
        liked_count=10,
        min_samples_per_centroid=2,
        dynamic_centroids=True,
        centroid_scaling_factor=0.4,
    )
    assert result == 4

    with pytest.raises(ValueError, match="liked_count must be positive"):
        _determine_centroid_count(
            liked_count=0,
            min_samples_per_centroid=2,
            dynamic_centroids=False,
            centroid_scaling_factor=0.5,
        )


def test_run_kmeans_validations():
    data = np.ones((2, 2), dtype=np.float64)
    with pytest.raises(ValueError, match="n_clusters=3"):
        _run_kmeans(data, n_clusters=3, random_state=0)

    mean_result = _run_kmeans(data, n_clusters=1, random_state=0)
    assert mean_result.shape == (1, 2)
    assert np.allclose(mean_result, np.ones((1, 2)))


def test_build_taste_vectors_with_dynamic_centroids(
    monkeypatch, sample_embedding, recommendation_config
):
    cfg = recommendation_config.model_copy(deep=True)
    cfg.taste_model.dynamic_centroids = True
    cfg.taste_model.centroid_scaling_factor = 0.5

    context = RecommendationContext(
        embedding=sample_embedding,
        config=cfg,
        embedding_columns=["taste_0", "taste_1"],
    )

    liked_matrix = np.arange(20, dtype=np.float64).reshape(10, 2)
    calls = {}

    def fake_run_kmeans(data, *, n_clusters, random_state):  # type: ignore[no-untyped-def]
        calls["clusters"] = n_clusters
        calls["random_state"] = random_state
        return np.full((n_clusters, data.shape[1]), 2.0, dtype=np.float64)

    monkeypatch.setattr("boardgame_recommender.recommend._run_kmeans", fake_run_kmeans)

    tastes = context.build_taste_vectors(liked_matrix)
    assert calls["clusters"] >= 1
    assert calls["random_state"] == cfg.random_seed
    assert tastes.shape[1] == 2
    norms = np.linalg.norm(tastes, axis=1)
    assert np.allclose(norms, 1.0)
