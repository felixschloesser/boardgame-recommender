from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

import pytest
from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.games.repository import BoardgameRepository
from boardgames_api.domain.participants.exceptions import ParticipantNotFoundError
from boardgames_api.domain.participants.records import Participant, StudyGroup
from boardgames_api.domain.participants.repository import ParticipantRepository
from boardgames_api.domain.recommendations.exceptions import (
    RecommendationNotFoundError,
    RecommendationUnauthorizedError,
    RecommendationUnavailableError,
)
from boardgames_api.domain.recommendations.models import (
    RecommendationResult,
    RecommendationSelection,
)
from boardgames_api.domain.recommendations.reccomender import ScoredGameId
from boardgames_api.domain.recommendations.repository import RecommendationRepository
from boardgames_api.domain.recommendations.schemas import (
    RecommendationExplanation,
    RecommendationRequest,
)
from boardgames_api.domain.recommendations.service import (
    generate_recommendations,
    get_recommendation,
)


class _StubParticipantRepo:
    def __init__(self, participant: Participant | None):
        self.participant = participant

    def get(self, participant_id: str):
        return (
            self.participant
            if self.participant and self.participant.participant_id == participant_id
            else None
        )


class _StubRecommendationRepo:
    def __init__(self):
        self.saved: RecommendationResult | None = None

    def save(self, result: RecommendationResult):
        self.saved = result

    def get(self, recommendation_id: str):
        if self.saved and self.saved.id == recommendation_id:
            return self.saved
        return None


class _StubBoardgameRepo:
    def __init__(self, ids: list[int]):
        self.ids = ids
        self.records = {
            i: BoardgameRecord(
                id=i,
                title=f"Game {i}",
                description="",
                mechanics=[],
                genre=[],
                themes=[],
                min_players=1,
                max_players=4,
                complexity=None,
                age_recommendation=None,
                num_user_ratings=None,
                avg_user_rating=None,
                year_published=None,
                playing_time_minutes=30,
                image_url="",
                bgg_url="",
            )
            for i in ids
        }

    def filter_ids_for_context(self, play_context, candidate_ids):
        return [cid for cid in candidate_ids if cid in self.ids]

    def get_many(self, ids: list[int]):
        return [self.records[i] for i in ids if i in self.records]


class _FakeRecommender:
    def __init__(self, ranked: list[ScoredGameId]):
        self.ranked = ranked

    def recommend(self, liked_games, num_results, candidate_ids=None):
        return self.ranked


class _FakeExplainer:
    def add_explanations(self, ranked, liked_games, boardgames=()):
        # Return dummy explanations matching ranked length
        from boardgames_api.domain.recommendations.schemas import RecommendationExplanation

        return [
            RecommendationExplanation(type="features", features=[], references=None) for _ in ranked
        ]


def _request():
    return RecommendationRequest.model_validate(
        {"liked_games": [1], "num_results": 2, "play_context": {"players": 2}}
    )


def test_generate_recommendations_happy_path():
    participant = Participant(participant_id="p1", study_group=StudyGroup.FEATURES)
    participant_repo = cast(ParticipantRepository, _StubParticipantRepo(participant))
    recommendation_repo_stub = _StubRecommendationRepo()
    recommendation_repo = cast(RecommendationRepository, recommendation_repo_stub)
    boardgame_repo = cast(BoardgameRepository, _StubBoardgameRepo(ids=[2, 3]))
    recommender = _FakeRecommender(ranked=[ScoredGameId(bgg_id=2, score=1.0)])
    request = _request()

    result = generate_recommendations(
        request,
        participant_id="p1",
        participant_repo=participant_repo,
        recommendation_repo=recommendation_repo,
        boardgame_repo=boardgame_repo,
        recommender=recommender,
    )
    assert result.selections
    assert result.selections[0].boardgame.id == 2
    # persisted
    assert recommendation_repo_stub.saved is not None


def test_generate_recommendations_raises_for_missing_participant():
    participant_repo = cast(ParticipantRepository, _StubParticipantRepo(participant=None))
    with pytest.raises(ParticipantNotFoundError):
        generate_recommendations(
            _request(),
            participant_id="missing",
            participant_repo=participant_repo,
            recommendation_repo=cast(RecommendationRepository, _StubRecommendationRepo()),
            boardgame_repo=cast(BoardgameRepository, _StubBoardgameRepo(ids=[])),
            recommender=_FakeRecommender([]),
        )


def test_generate_recommendations_raises_when_filtered_empty():
    participant = Participant(participant_id="p1", study_group=StudyGroup.FEATURES)
    participant_repo = cast(ParticipantRepository, _StubParticipantRepo(participant))
    boardgame_repo = cast(BoardgameRepository, _StubBoardgameRepo(ids=[]))
    ranker = _FakeRecommender(ranked=[ScoredGameId(bgg_id=99, score=1.0)])
    with pytest.raises(RecommendationUnavailableError):
        generate_recommendations(
            _request(),
            participant_id="p1",
            participant_repo=participant_repo,
            recommendation_repo=cast(RecommendationRepository, _StubRecommendationRepo()),
            boardgame_repo=boardgame_repo,
            recommender=ranker,
        )


def test_generate_recommendations_raises_when_hydration_missing():
    participant = Participant(participant_id="p1", study_group=StudyGroup.FEATURES)
    participant_repo = cast(ParticipantRepository, _StubParticipantRepo(participant))
    ranker = _FakeRecommender(ranked=[ScoredGameId(bgg_id=42, score=1.0)])
    request = _request()

    class _BrokenBoardgameRepo:
        def filter_ids_for_context(self, play_context, candidate_ids):
            return candidate_ids

        def get_many(self, ids: list[int]):
            return []

    with pytest.raises(RecommendationUnavailableError):
        generate_recommendations(
            request,
            participant_id="p1",
            participant_repo=participant_repo,
            recommendation_repo=cast(RecommendationRepository, _StubRecommendationRepo()),
            boardgame_repo=cast(BoardgameRepository, _BrokenBoardgameRepo()),
            recommender=ranker,
        )


def test_get_recommendation_happy_path():
    participant = Participant(participant_id="p1", study_group=StudyGroup.FEATURES)
    selection = RecommendationSelection(
        boardgame=BoardgameRecord(
            id=1,
            title="t",
            description="",
            mechanics=[],
            genre=[],
            themes=[],
            min_players=1,
            max_players=1,
            complexity=None,
            age_recommendation=None,
            num_user_ratings=None,
            avg_user_rating=None,
            year_published=None,
            playing_time_minutes=10,
            image_url="",
            bgg_url="",
        ),
        explanation=RecommendationExplanation(type="features", features=[], references=None),
    )
    rec = RecommendationResult(
        id="rec-1",
        participant_id=participant.participant_id,
        created_at=datetime.now(timezone.utc),
        intent=_request(),
        model_version="v1",
        experiment_group=participant.study_group,
        selections=[selection],
    )
    repo = cast(RecommendationRepository, _StubRecommendationRepo())
    repo.save(rec)
    got = get_recommendation("rec-1", participant.participant_id, repo)
    assert got.id == "rec-1"


def test_get_recommendation_not_found():
    repo = cast(RecommendationRepository, _StubRecommendationRepo())
    with pytest.raises(RecommendationNotFoundError):
        get_recommendation("missing", "p", repo)


def test_get_recommendation_unauthorized():
    participant = Participant(participant_id="owner", study_group=StudyGroup.FEATURES)
    selection = RecommendationSelection(
        boardgame=BoardgameRecord(
            id=1,
            title="t",
            description="",
            mechanics=[],
            genre=[],
            themes=[],
            min_players=1,
            max_players=1,
            complexity=None,
            age_recommendation=None,
            num_user_ratings=None,
            avg_user_rating=None,
            year_published=None,
            playing_time_minutes=10,
            image_url="",
            bgg_url="",
        ),
        explanation=RecommendationExplanation(type="features", features=[], references=None),
    )
    rec = RecommendationResult(
        id="rec-1",
        participant_id=participant.participant_id,
        created_at=None,  # type: ignore[arg-type]
        intent=_request(),
        model_version="v1",
        experiment_group=participant.study_group,
        selections=[selection],
    )
    repo = cast(RecommendationRepository, _StubRecommendationRepo())
    repo.save(rec)
    with pytest.raises(RecommendationUnauthorizedError):
        get_recommendation("rec-1", "other", repo)
