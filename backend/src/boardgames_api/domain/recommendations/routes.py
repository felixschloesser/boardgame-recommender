from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Security

from boardgames_api.domain.participants.service import get_participant
from boardgames_api.domain.recommendations import service as recommendation_service
from boardgames_api.domain.recommendations.schemas import (
    Recommendation,
    RecommendationRequest,
)
from boardgames_api.http.auth import require_session
from boardgames_api.http.dependencies import db_session
from boardgames_api.http.errors.schemas import ProblemDetailsResponse

router = APIRouter()


@router.post(
    "/recommendation",
    response_model=Recommendation,
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
    db=Depends(db_session),
    payload: RecommendationRequest = Body(...),
) -> Recommendation:
    """
    Generate recommendations for a participant based on their preferences.

    Note: session_id here is the authenticated participant_id (set in the session cookie).
    """
    participant = get_participant(session_id, db=db)
    study_group = participant.study_group
    return recommendation_service.generate_recommendations(
        payload,
        participant_id=session_id,
        study_group=study_group,
        db=db,
    )


@router.get(
    "/recommendation/{recommendation_id}",
    response_model=Recommendation,
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
    db=Depends(db_session),
) -> Recommendation:
    """
    Retrieve a stored recommendation by its identifier.
    """
    return recommendation_service.get_recommendation(
        recommendation_id,
        participant_id,
        db,
    )
