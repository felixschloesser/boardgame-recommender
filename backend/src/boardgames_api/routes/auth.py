from typing import Any

from fastapi import APIRouter, Body, Cookie, Response
from fastapi.responses import JSONResponse

from boardgames_api.models.auth import Participant
from boardgames_api.models.common import ProblemDetails
from boardgames_api.services.auth import create_session, terminate_session

router = APIRouter()

# Request and response models are now imported from `backend.models.auth`


@router.post(
    "/session",
    response_model=Participant,
    responses={400: {"model": ProblemDetails, "description": "Invalid study token."}},
)
async def create_participant_session(
    response: Response, payload: Any = Body(default=None)
) -> Participant | JSONResponse:
    """
    Create a new participant session using a study token.
    Issues a session cookie upon successful creation.
    """
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content=ProblemDetails(
                type="about:blank",
                title="Invalid study token",
                status=400,
                detail="Request body must be an object.",
                code=None,
                instance=None,
                invalid_params=None,
            ).model_dump(exclude_none=True),
        )

    study_token = payload.get("study_token", "")
    if "study_token" not in payload or not isinstance(study_token, str) or study_token == "":
        return JSONResponse(
            status_code=400,
            content=ProblemDetails(
                type="about:blank",
                title="Invalid study token",
                status=400,
                detail="A non-empty study_token string is required.",
                code=None,
                instance=None,
                invalid_params=None,
            ).model_dump(exclude_none=True),
        )

    try:
        participant = create_session(study_token)
        response.set_cookie(key="session_id", value=str(participant["participant_id"]))
        return Participant.model_validate(participant)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content=ProblemDetails(
                type="about:blank",
                title="Invalid study token",
                status=400,
                detail=str(e),
                code=None,
                instance=None,
                invalid_params=None,
            ).model_dump(exclude_none=True),
        )


@router.delete(
    "/session",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={401: {"model": ProblemDetails, "description": "Unauthorized."}},
)
async def terminate_participant_session(
    session_id: str = Cookie(default=None),
) -> Response | JSONResponse:
    """
    Terminate the current participant session.
    """
    if not session_id:
        problem = ProblemDetails(
            type="about:blank",
            title="Unauthorized",
            status=401,
            detail="Session ID missing.",
            code=None,
            instance=None,
            invalid_params=None,
        )
        return JSONResponse(
            status_code=401, content=problem.model_dump(exclude_none=True)
        )

    try:
        terminate_session(session_id)
    except ValueError as exc:
        problem = ProblemDetails(
            type="about:blank",
            title="Unauthorized",
            status=401,
            detail=str(exc),
            code=None,
            instance=None,
            invalid_params=None,
        )
        return JSONResponse(
            status_code=401, content=problem.model_dump(exclude_none=True)
        )

    return Response(status_code=204)
