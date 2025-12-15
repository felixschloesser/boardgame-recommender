import logging
import os
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Security

from boardgames_api.domain.participants.records import StudyGroup
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
logger = logging.getLogger(__name__)

_OVERRIDE_RAW = os.getenv("RECOMMENDATION_OVERRIDE")
_OVERRIDE_STUDY_GROUP: StudyGroup | None
if _OVERRIDE_RAW:
    match _OVERRIDE_RAW.lower():
        case "features":
            _OVERRIDE_STUDY_GROUP = StudyGroup.FEATURES
        case "references":
            _OVERRIDE_STUDY_GROUP = StudyGroup.REFERENCES
        case _:
            _OVERRIDE_STUDY_GROUP = None
            logger.warning(
                "Invalid RECOMMENDATION_OVERRIDE value: %s (expected 'features' or 'references')",
                _OVERRIDE_RAW,
            )
    if _OVERRIDE_STUDY_GROUP:
        logger.info("RECOMMENDATION_OVERRIDE active: %s", _OVERRIDE_STUDY_GROUP.value)
else:
    _OVERRIDE_STUDY_GROUP = None


def _override_study_group() -> StudyGroup | None:
    return _OVERRIDE_STUDY_GROUP


# Expose override values for startup logging elsewhere (e.g., app.py).
OVERRIDE_RAW = _OVERRIDE_RAW
OVERRIDE_STUDY_GROUP = _OVERRIDE_STUDY_GROUP


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
    study_group = _override_study_group() or participant.study_group
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
