import random
import uuid

from sqlalchemy.orm import Session

from boardgames_api.domain.participants.exceptions import (
    ParticipantAlreadyExistsError,
    ParticipantNotFoundError,
    ParticipantValidationError,
)
from boardgames_api.domain.participants.records import Participant, StudyGroup
from boardgames_api.domain.participants.repository import ParticipantRepository


def create_session(db: Session) -> Participant:
    """
    Create a new participant with a stable identifier and assigned study group.
    """
    participant_id = _new_participant_id()
    study_group = assign_study_group()

    participant = Participant(participant_id=participant_id, study_group=study_group)
    repo = ParticipantRepository(db)
    if repo.get(participant_id):
        raise ParticipantAlreadyExistsError("Participant already exists.")
    repo.save(participant)
    return participant


def _new_participant_id() -> str:
    """
    Generate a participant identifier that is UUID-based but clearly labeled.
    """
    return f"participant-{uuid.uuid4()}"


def assign_study_group() -> StudyGroup:
    """
    Randomly assign a study group on first session creation.
    """
    return random.choice([StudyGroup.FEATURES, StudyGroup.REFERENCES])


def get_participant(participant_id: str, db: Session) -> Participant:
    """
    Load a participant by id or raise if not found.
    """
    if not participant_id or not participant_id.startswith("participant-"):
        raise ParticipantValidationError(
            "participant_id is required and must start with 'participant-'."
        )
    repo = ParticipantRepository(db)
    participant = repo.get(participant_id)
    if participant is None:
        raise ParticipantNotFoundError("Participant not found.")
    return participant
