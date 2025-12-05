from fastapi import APIRouter, Body, Depends, Request, Response, Security

from boardgames_api.domain.participants.schemas import (
    ParticipantCreateRequest,
    ParticipantResponse,
    SessionCreateRequest,
)
from boardgames_api.domain.participants.service import create_session, get_participant
from boardgames_api.http.auth import invalidate_session
from boardgames_api.http.dependencies import db_session
from boardgames_api.http.errors.schemas import ProblemDetailsResponse

router = APIRouter()


@router.post(
    "/session",
    response_model=ParticipantResponse,
    responses={
        400: {"model": ProblemDetailsResponse, "description": "Invalid request body."},
        404: {"model": ProblemDetailsResponse, "description": "Participant not found."},
    },
)
def create_participant_session(
    request: Request,
    db=Depends(db_session),
    payload: SessionCreateRequest = Body(...),
) -> ParticipantResponse:
    """
    Create a new participant session with a stable participant id and assigned study group.
    Issues a session cookie upon successful creation.
    """
    participant_id_val = payload.participant_id
    participant = get_participant(participant_id_val, db=db)

    request.session.update(
        {
            "participant_id": participant.participant_id,
            "study_group": participant.study_group.value if participant.study_group else None,
        }
    )
    return ParticipantResponse.model_validate(
        {
            "participant_id": participant.participant_id,
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


@router.post(
    "/participant",
    response_model=ParticipantResponse,
    status_code=201,
    responses={
        400: {"model": ProblemDetailsResponse, "description": "Invalid request body."}
    },
)
def create_participant(
    db=Depends(db_session),
    payload: ParticipantCreateRequest = Body(...),
) -> ParticipantResponse:
    """
    Create a new participant with a stable id and assigned study group.
    """
    participant = create_session(db=db)
    return ParticipantResponse.model_validate(
        {
            "participant_id": participant.participant_id,
        }
    )
