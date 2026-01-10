import logging
import os
import random
import uuid
from enum import Enum

from sqlalchemy.orm import Session

from boardgames_api.domain.participants.exceptions import (
    ParticipantAlreadyExistsError,
    ParticipantNotFoundError,
    ParticipantValidationError,
)
from boardgames_api.domain.participants.records import Participant, StudyGroup
from boardgames_api.domain.participants.repository import ParticipantRepository

logger = logging.getLogger("uvicorn.error")
_missing_mode_warning_emitted = False
_ENV_VAR = "PARTICIPANT_ASSIGNMENT_MODE"


class StudyGroupMode(str, Enum):
    RANDOM = "random"
    FORCE_REFERENCES = "force_references"
    FORCE_FEATURES = "force_features"


def create_session(db: Session) -> Participant:
    """
    Create a new participant with a stable identifier and assigned study group.
    """
    participant_id = _new_participant_id()
    mode = get_study_group_mode()
    study_group = assign_study_group(mode)
    logger.info(
        "create_session: participant_id=%s group=%s mode=%s",
        participant_id,
        study_group.name,
        mode.name,
    )

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


def get_study_group_mode() -> StudyGroupMode:
    """
    Resolve the study group assignment mode from the environment, defaulting to RANDOM.
    """
    global _missing_mode_warning_emitted
    raw_mode = os.getenv(_ENV_VAR)
    if raw_mode is None:
        if not _missing_mode_warning_emitted:
            logger.warning(
                "%s not set, defaulting to RANDOM (participant assignment)",
                _ENV_VAR,
            )
            _missing_mode_warning_emitted = True
        return StudyGroupMode.RANDOM

    normalized = raw_mode.strip().lower()
    for mode in StudyGroupMode:
        if normalized in {mode.value, mode.name.lower()}:
            return mode

    logger.warning(
        "Invalid %s=%s, defaulting to RANDOM (participant assignment)",
        _ENV_VAR,
        raw_mode,
    )
    return StudyGroupMode.RANDOM


def assign_study_group(mode: StudyGroupMode | None = None) -> StudyGroup:
    """
    Assign a study group based on configured mode.
    """
    resolved_mode = mode or get_study_group_mode()
    if resolved_mode == StudyGroupMode.FORCE_REFERENCES:
        return StudyGroup.REFERENCES
    if resolved_mode == StudyGroupMode.FORCE_FEATURES:
        return StudyGroup.FEATURES
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
