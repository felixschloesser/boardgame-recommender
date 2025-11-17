from __future__ import annotations

import pytest

from boardgame_recommender.pipelines.training import train
from boardgame_recommender.recommend import recommend_games


@pytest.mark.end_to_end
def test_end_to_end_training_and_recommendation(sample_features, config):
    embedding = train(features=sample_features, config=config)

    recommendation_config = config.recommendation.model_copy(deep=True)
    results = recommend_games(
        embedding=embedding,
        liked_games=["Alpha", "Beta"],
        player_count=2,
        available_time_minutes=120,
        amount=3,
        config=recommendation_config,
    )

    assert results, "Expected recommendations from trained embedding."
    assert all(result["name"] not in {"Alpha", "Beta"} for result in results)
    assert len(results) <= 3
