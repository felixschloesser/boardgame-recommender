from pydantic import BaseModel, Field


class ParticipantResponse(BaseModel):
    """
    Response schema for a participant session.
    """

    participant_id: str
    study_group: str


class SessionCreateRequest(BaseModel):
    """
    Request payload for creating a participant session.
    """

    study_token: str = Field(..., min_length=1)
