from typing import Any, Optional

from pydantic import BaseModel, Field


class Participant(BaseModel):
    """
    Response schema for a participant session.
    """

    participant_id: str
    study_group: Optional[str] = None


class SessionCreateRequest(BaseModel):
    """
    Request payload for creating a participant session.
    """

    study_token: Any = Field(default="")
