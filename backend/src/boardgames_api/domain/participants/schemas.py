from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParticipantResponse(BaseModel):
    """
    Response schema for a participant session.
    """

    model_config = ConfigDict(extra="forbid")
    participant_id: str


class SessionCreateRequest(BaseModel):
    """
    Request payload for creating a participant session.
    """

    model_config = ConfigDict(extra="forbid")
    participant_id: str = Field(
        ...,
        description="Participant id to resume a session.",
        pattern="^participant-",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_null_participant_id(cls, data):
        if isinstance(data, dict):
            val = data.get("participant_id")
            if val is None:
                raise ValueError("participant_id must be provided.")
        return data


class ParticipantCreateRequest(BaseModel):
    """
    Request payload for creating a new participant.
    """

    model_config = ConfigDict(extra="forbid")
