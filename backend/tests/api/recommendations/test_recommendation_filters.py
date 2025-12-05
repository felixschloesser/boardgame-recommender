from __future__ import annotations

import random

import pytest
from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.schemas import PlayDuration, RecommendationRequest
from boardgames_api.domain.recommendations.service import generate_recommendations
from boardgames_api.utils import embedding as embedding_utils

from boardgames_api.domain.recommendations import service as recommendation_service


def _fake_game(
    game_id: int, *, min_players: int, max_players: int, minutes: int
) -> BoardGameResponse:
    return BoardGameResponse(
        id=str(game_id),
        title=f"Game {game_id}",
        description="test",
        mechanics=[],
        genre=[],
        themes=[],
        min_players=min_players,
        max_players=max_players,
        complexity=1.0,
        age_recommendation=8,
        num_user_ratings=10,
        avg_user_rating=7.0,
        year_published=2020,
        playing_time_minutes=minutes,
        image_url="http://example.com",
        bgg_url="http://example.com",
    )


@pytest.fixture(autouse=True)
def clear_embedding_store(monkeypatch):
    monkeypatch.setattr(embedding_utils, "_store", None, raising=False)


class _FakeStore:
    def __init__(self, run_identifier: str = "test"):
        self.run_identifier = run_identifier

    def has_id(self, bgg_id: int) -> bool:
        return True

    def get_name(self, bgg_id: int) -> str | None:
        return f"Game {bgg_id}"

    def score_candidates(self, liked_ids, candidate_ids):  # type: ignore[no-untyped-def]
        # Simple deterministic score: higher id wins
        return {int(cid): float(cid) for cid in candidate_ids}


def test_generate_filters_by_players_and_duration(monkeypatch):
    games = [
        _fake_game(1, min_players=2, max_players=4, minutes=30),  # eligible
        _fake_game(2, min_players=5, max_players=6, minutes=30),  # too many players
        _fake_game(3, min_players=2, max_players=4, minutes=200),  # too long
    ]

    monkeypatch.setattr(
        recommendation_service,
        "_fetch_candidates",
        lambda play_context, desired_results, db: [games[0]],
    )
    monkeypatch.setattr(recommendation_service, "get_embedding_index", lambda: _FakeStore())
    monkeypatch.setattr(random, "sample", lambda seq, k: list(seq)[:k])  # deterministic fallback
    from boardgames_api.persistence.database import session_scope

    request = RecommendationRequest.model_validate(
        {
            "liked_games": [99],
            "num_results": 2,
            "play_context": {"players": 3, "duration": PlayDuration.SHORT},
        }
    )

    with session_scope() as session:
        result = generate_recommendations(
            request,
            participant_id="participant-test",
            study_group=StudyGroup.REFERENCES,
            db=session,
        )
    assert len(result.recommendations) == 1
    assert result.recommendations[0].boardgame.id == "1"


def test_embedding_store_prefers_env_run(monkeypatch, tmp_path):
    run_a = tmp_path / "runA"
    run_b = tmp_path / "runB"
    for folder in (run_a, run_b):
        folder.mkdir()
        (folder / "vectors.parquet").write_text("")  # placeholder
    # Create minimal parquet with embedding columns in runB only.
    import polars as pl

    df = pl.DataFrame(
        {
            "bgg_id": [1],
            "name": ["X"],
            "embedding_dimension_0": [1.0],
            "embedding_dimension_1": [0.0],
        }
    )
    df.write_parquet(run_b / "vectors.parquet")

    monkeypatch.setenv("BOARDGAMES_EMBEDDING_RUN", "runB")
    monkeypatch.setattr(embedding_utils, "DEFAULT_EMBEDDINGS_DIR", tmp_path)
    monkeypatch.setattr(embedding_utils, "_store", None, raising=False)

    store = embedding_utils.get_embedding_store()
    assert store is not None
    assert store.run_identifier == "runB"
