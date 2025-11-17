from __future__ import annotations

import numpy as np
import pytest

from boardgame_recommender.recommend import RecommendationContext, recommend_games


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
