import os
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Security

from boardgames_api.domain.games.repository import BoardgameRepository
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.participants.repository import ParticipantRepository
from boardgames_api.domain.recommendations import service as recommendation_service
from boardgames_api.domain.recommendations.reccomender import EmbeddingSimilarityRecommender
from boardgames_api.domain.recommendations.repository import RecommendationRepository
from boardgames_api.domain.recommendations.schemas import (
    RecommendationRequest,
    RecommendationResponse,
)
from boardgames_api.http.auth import require_session
from boardgames_api.http.dependencies import db_session
from boardgames_api.http.errors.schemas import ProblemDetailsResponse

router = APIRouter()


def _load_override(env_value: str | None) -> StudyGroup | None:
    if not env_value:
        return None
    try:
        return StudyGroup(env_value.lower())
    except ValueError:
        return None


# Expose override values for startup logging elsewhere (e.g., app.py).
OVERRIDE_RAW = os.getenv("RECOMMENDATION_OVERRIDE")
OVERRIDE_STUDY_GROUP = _load_override(OVERRIDE_RAW)


def _participant_repo(db=Depends(db_session)) -> ParticipantRepository:
    return ParticipantRepository(db)


def _recommendation_repo(db=Depends(db_session)) -> RecommendationRepository:
    return RecommendationRepository(db)


def _boardgame_repo(db=Depends(db_session)) -> BoardgameRepository:
    return BoardgameRepository(db)


def _suggester() -> EmbeddingSimilarityRecommender:
    return EmbeddingSimilarityRecommender()


@router.post(
    "/recommendation",
    response_model=RecommendationResponse,
    status_code=201,
    responses={
        400: {"model": ProblemDetailsResponse, "description": "Invalid request."},
        401: {"model": ProblemDetailsResponse, "description": "Unauthorized."},
        503: {
            "model": ProblemDetailsResponse,
            "description": "Recommender unavailable.",
        },
    },
)
def create_recommendation(
    request: Request,
    session_id: Annotated[str, Security(require_session, use_cache=False)],
    payload: RecommendationRequest = Body(...),
    participant_repo: ParticipantRepository = Depends(_participant_repo),
    recommendation_repo: RecommendationRepository = Depends(_recommendation_repo),
    boardgame_repo: BoardgameRepository = Depends(_boardgame_repo),
    suggester: EmbeddingSimilarityRecommender = Depends(_suggester),
) -> RecommendationResponse:
    """
    Generate recommendations for a participant based on their preferences.

    Note: session_id here is the authenticated participant_id (set in the session cookie).
    """
    recommendation = recommendation_service.generate_recommendations(
        payload,
        participant_id=session_id,
        participant_repo=participant_repo,
        recommendation_repo=recommendation_repo,
        boardgame_repo=boardgame_repo,
        recommender=suggester,
        study_group_override=OVERRIDE_STUDY_GROUP,
    )
    return RecommendationResponse.from_domain(recommendation)


@router.get(
    "/recommendation/{recommendation_id}",
    response_model=RecommendationResponse,
    responses={
        401: {"model": ProblemDetailsResponse, "description": "Unauthorized."},
        404: {
            "model": ProblemDetailsResponse,
            "description": "Recommendation not found.",
        },
    },
)
def get_recommendation(
    recommendation_id: str,
    participant_id: Annotated[str, Security(require_session, use_cache=False)],
    recommendation_repo: RecommendationRepository = Depends(_recommendation_repo),
) -> RecommendationResponse:
    """
    Retrieve a stored recommendation by its identifier.
    """
    recommendation = recommendation_service.get_recommendation(
        recommendation_id,
        participant_id,
        recommendation_repo=recommendation_repo,
    )
    return RecommendationResponse.from_domain(recommendation)
