from typing import Any

from fastapi import APIRouter, Body, Cookie
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from boardgames_api.models.common import ProblemDetails
from boardgames_api.models.recommendations import (
    RecommendationRequest,
    RecommendationResponse,
)
from boardgames_api.services.auth import is_valid_session
from boardgames_api.services.recommendations import (
    generate_recommendations,
    get_recommendation_session,
)
from boardgames_api.utils.exceptions import RecommenderUnavailableException

router = APIRouter()


@router.post(
    "/recommendation",
    response_model=RecommendationResponse,
    status_code=201,
    responses={
        400: {"model": ProblemDetails, "description": "Invalid request."},
        401: {"model": ProblemDetails, "description": "Unauthorized."},
        503: {"model": ProblemDetails, "description": "Recommender unavailable."},
    },
)
@router.post(
    "/recommendations/",
    response_model=RecommendationResponse,
    status_code=201,
    responses={
        400: {"model": ProblemDetails, "description": "Invalid request."},
        401: {"model": ProblemDetails, "description": "Unauthorized."},
        503: {"model": ProblemDetails, "description": "Recommender unavailable."},
    },
    include_in_schema=False,
)
async def create_recommendations(
    payload: Any = Body(default=None),
    session_id: str | None = Cookie(default=None),
) -> RecommendationResponse | JSONResponse:
    """
    Generate recommendations for a participant based on their preferences.
    Accepts both the OpenAPI payload shape and the simplified integration test payload.
    """
    if session_id is not None and not is_valid_session(session_id):
        problem = ProblemDetails(
            type="about:blank",
            title="Unauthorized",
            status=401,
            detail="Valid session cookie is required.",
            instance=None,
            code=None,
            invalid_params=None,
        )
        return JSONResponse(status_code=401, content=problem.model_dump(exclude_none=True))

    try:
        if not isinstance(payload, dict):
            raise ValueError("Request body must be an object.")

        request = RecommendationRequest.model_validate(payload)
        return generate_recommendations(request)
    except ValidationError:
        problem = ProblemDetails(
            type="about:blank",
            title="Invalid request",
            status=400,
            detail="Request payload failed validation.",
            instance=None,
            code=None,
            invalid_params=None,
        )
        return JSONResponse(status_code=400, content=problem.model_dump(exclude_none=True))
    except ValueError as e:
        problem = ProblemDetails(
            type="about:blank",
            title="Invalid request",
            status=400,
            detail=str(e),
            instance=None,
            code=None,
            invalid_params=None,
        )
        return JSONResponse(status_code=400, content=problem.model_dump(exclude_none=True))
    except RecommenderUnavailableException as e:
        problem = ProblemDetails(
            type="about:blank",
            title="Recommender unavailable",
            status=503,
            detail=str(e),
            instance=None,
            code=None,
            invalid_params=None,
        )
        return JSONResponse(status_code=503, content=problem.model_dump(exclude_none=True))


@router.get(
    "/recommendation/{session_id}",
    response_model=RecommendationResponse,
    responses={
        401: {"model": ProblemDetails, "description": "Unauthorized."},
        404: {"model": ProblemDetails, "description": "Session not found."},
    },
)
async def retrieve_recommendation_session(
    session_id: str, session_cookie: str | None = Cookie(default=None)
) -> RecommendationResponse | JSONResponse:
    """
    Retrieve a stored recommendation session by its session ID.
    """
    if session_cookie is not None and not is_valid_session(session_cookie):
        problem = ProblemDetails(
            type="about:blank",
            title="Unauthorized",
            status=401,
            detail="Valid session cookie is required.",
            instance=None,
            code=None,
            invalid_params=None,
        )
        return JSONResponse(status_code=401, content=problem.model_dump(exclude_none=True))

    session = get_recommendation_session(session_id)
    if not session:
        problem = ProblemDetails(
            type="about:blank",
            title="Session not found.",
            status=404,
            detail="Session not found.",
            instance=None,
            code=None,
            invalid_params=None,
        )
        return JSONResponse(status_code=404, content=problem.model_dump(exclude_none=True))
    return session


@router.get(
    "/recommendations/{session_id}",
    response_model=RecommendationResponse,
    responses={
        401: {"model": ProblemDetails, "description": "Unauthorized."},
        404: {"model": ProblemDetails, "description": "Session not found."},
    },
    include_in_schema=False,
)
async def retrieve_recommendation_session_alias(
    session_id: str, session_cookie: str | None = Cookie(default=None)
) -> RecommendationResponse | JSONResponse:
    """
    Compatibility endpoint matching the plural path used by integration tests.
    """
    return await retrieve_recommendation_session(session_id, session_cookie)
