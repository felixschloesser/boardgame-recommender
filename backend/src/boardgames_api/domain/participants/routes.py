from fastapi import APIRouter, Body, Request, Response, Security

from boardgames_api.domain.participants.schemas import ParticipantResponse, SessionCreateRequest
from boardgames_api.domain.participants.service import create_session
from boardgames_api.http.auth import invalidate_session
from boardgames_api.http.errors.schemas import ProblemDetailsResponse

router = APIRouter()


@router.post(
    "/session",
    response_model=ParticipantResponse,
    responses={
        400: {"model": ProblemDetailsResponse, "description": "Invalid study token."}
    },
)
def create_participant_session(
    request: Request, response: Response, payload: SessionCreateRequest = Body(...)
) -> ParticipantResponse:
    """
    Create a new participant session using a study token.
    Issues a session cookie upon successful creation.
    """
    session_record = create_session(payload.study_token)
    request.session.update(
        {
            "participant_id": session_record.participant_id,
            "study_group": session_record.study_group,
        }
    )
    return ParticipantResponse.model_validate(
        {
            "participant_id": session_record.participant_id,
            "study_group": session_record.study_group,
        }
    )


@router.delete(
    "/session",
    status_code=204,
    response_class=Response,
    response_model=None,
    responses={401: {"model": ProblemDetailsResponse, "description": "Unauthorized."}},
)
def terminate_participant_session(
    session_id: str = Security(invalidate_session, use_cache=False),
) -> Response:
    """
    Terminate the current participant session.
    """
    response = Response(status_code=204)
    response.delete_cookie(key="session_id", samesite="lax")
    return response
