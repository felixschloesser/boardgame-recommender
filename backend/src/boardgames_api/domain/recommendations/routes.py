from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Security
from starlette import status

from boardgames_api.domain.recommendations.exceptions import (
    RecommendationInputError,
    RecommendationNotFoundError,
    RecommendationUnavailableError,
)
from boardgames_api.domain.recommendations.schemas import Recommendation, RecommendationRequest
from boardgames_api.domain.recommendations.service import (
    generate_recommendations,
    get_recommendation_snapshot,
)
from boardgames_api.http.auth import require_session
from boardgames_api.http.errors.schemas import ProblemDetailsResponse

router = APIRouter()


@router.post(
    "/recommendation",
    response_model=Recommendation,
    status_code=201,
    responses={
        400: {"model": ProblemDetailsResponse, "description": "Invalid request."},
        401: {"model": ProblemDetailsResponse, "description": "Unauthorized."},
        503: {"model": ProblemDetailsResponse, "description": "Recommender unavailable."},
    },
)
@router.post(
    "/recommendations/",
    response_model=Recommendation,
    status_code=201,
    responses={
        400: {"model": ProblemDetailsResponse, "description": "Invalid request."},
        401: {"model": ProblemDetailsResponse, "description": "Unauthorized."},
        503: {"model": ProblemDetailsResponse, "description": "Recommender unavailable."},
    },
    include_in_schema=False,
)
def create_recommendations(
    session_id: Annotated[str, Security(require_session, use_cache=False)],
    payload: RecommendationRequest = Body(...),
) -> Recommendation:
    """
    Generate recommendations for a participant based on their preferences.
    Accepts both the OpenAPI payload shape and the simplified integration test payload.
    """
    if payload.num_results <= 0 or payload.num_results > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="num_results must be between 1 and 100.",
        )
    if not payload.liked_games:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="liked_games must contain at least one game ID.",
        )
    if any(game_id <= 0 for game_id in payload.liked_games):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="liked_games entries must be positive integers.",
        )
    try:
        return generate_recommendations(payload)
    except RecommendationInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except RecommendationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


@router.get(
    "/recommendation/{recommendation_id}",
    response_model=Recommendation,
    responses={
        401: {"model": ProblemDetailsResponse, "description": "Unauthorized."},
        404: {"model": ProblemDetailsResponse, "description": "Recommendation not found."},
    },
)
def retrieve_recommendation(
    recommendation_id: str,
    session_cookie: Annotated[str, Security(require_session, use_cache=False)],
) -> Recommendation:
    """
    Retrieve a stored recommendation by its identifier.
    """
    try:
        return get_recommendation_snapshot(recommendation_id)
    except RecommendationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/recommendations/{recommendation_id}",
    response_model=Recommendation,
    responses={
        401: {"model": ProblemDetailsResponse, "description": "Unauthorized."},
        404: {"model": ProblemDetailsResponse, "description": "Recommendation not found."},
    },
    include_in_schema=False,
)
def retrieve_recommendation_alias(
    recommendation_id: str,
    session_cookie: Annotated[str, Security(require_session, use_cache=False)],
) -> Recommendation:
    """
    Compatibility endpoint matching the plural path used by integration tests.
    """
    return retrieve_recommendation(recommendation_id, session_cookie)
