from __future__ import annotations

import random
from typing import cast

import pytest
from boardgames_api.domain.games.repository import BoardgameRepository
from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.domain.participants.records import Participant, StudyGroup
from boardgames_api.domain.participants.repository import ParticipantRepository
from boardgames_api.domain.recommendations.reccomender import ScoredGameId
from boardgames_api.domain.recommendations.repository import RecommendationRepository
from boardgames_api.domain.recommendations.schemas import PlayDuration, RecommendationRequest
from boardgames_api.domain.recommendations.service import generate_recommendations
from boardgames_api.infrastructure import embeddings as embedding_utils


def _fake_game(game_id: int, min_players: int, max_players: int, minutes: int) -> BoardGameResponse:
    return BoardGameResponse(
        id=game_id,
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


class _StubParticipantRepo:
    def __init__(self, participant: Participant):
        self.participant = participant

    def get(self, participant_id: str) -> Participant | None:
        return self.participant if participant_id == self.participant.participant_id else None


class _StubRecommendationRepo:
    def __init__(self):
        self.saved = None

    def save(self, result):
        self.saved = result

    def get(self, recommendation_id: str):
        if self.saved and getattr(self.saved, "id", None) == recommendation_id:
            return self.saved
        return None


class _FakeRecommender:
    def __init__(self, ranked: list[ScoredGameId] | None = None):
        self.ranked = ranked or [
            ScoredGameId(bgg_id=1, score=1.0),
            ScoredGameId(bgg_id=2, score=0.5),
            ScoredGameId(bgg_id=3, score=0.1),
        ]

    def recommend(self, liked_games, num_results):
        return self.ranked[:num_results]


class _StubBoardgameRepo:
    def __init__(self, games: list[BoardGameResponse]):
        self.games = games

    def filter_ids_for_context(self, play_context, candidate_ids):
        players = getattr(play_context, "players", None) if play_context else None
        duration = getattr(play_context, "duration", None)
        max_minutes = None
        if duration is not None:
            max_minutes = {
                PlayDuration.SHORT: 45,
                PlayDuration.MEDIUM: 90,
                PlayDuration.LONG: 240,
            }.get(duration, None)

        filtered: list[int] = []
        for cid in candidate_ids:
            game = next((g for g in self.games if g.id == cid), None)
            if not game:
                continue
            if players is not None and not (game.min_players <= players <= game.max_players):
                continue
            if max_minutes is not None and game.playing_time_minutes > max_minutes:
                continue
            filtered.append(cid)
        return filtered

    def get_many(self, ids: list[int]):
        return [g for g in self.games if g.id in ids]


def test_generate_filters_by_players_and_duration(monkeypatch):
    games = [
        _fake_game(1, min_players=2, max_players=4, minutes=30),  # eligible
        _fake_game(2, min_players=5, max_players=6, minutes=30),  # too many players
        _fake_game(3, min_players=2, max_players=4, minutes=200),  # too long
    ]

    monkeypatch.setattr(random, "sample", lambda seq, k: list(seq)[:k])  # deterministic fallback

    request = RecommendationRequest.model_validate(
        {
            "liked_games": [99],
            "num_results": 2,
            "play_context": {"players": 3, "duration": PlayDuration.SHORT},
        }
    )

    participant = Participant(participant_id="participant-test", study_group=StudyGroup.REFERENCES)
    participant_repo = cast(ParticipantRepository, _StubParticipantRepo(participant))
    recommendation_repo = cast(RecommendationRepository, _StubRecommendationRepo())
    result = generate_recommendations(
        request,
        participant_id="participant-test",
        participant_repo=participant_repo,
        recommendation_repo=recommendation_repo,
        boardgame_repo=cast(BoardgameRepository, _StubBoardgameRepo([games[0]])),
        recommender=_FakeRecommender(),
    )
    assert len(result.selections) == 1
    assert result.selections[0].boardgame.id == 1


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

    store = embedding_utils.load_embedding(use_cache=False)
    assert store is not None
    assert store.run_identifier == "runB"
