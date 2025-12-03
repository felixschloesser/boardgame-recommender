import uuid

from boardgames_api.domain.participants.exceptions import InvalidStudyTokenError
from boardgames_api.domain.participants.records import ParticipantRecord


def create_session(study_token: str) -> ParticipantRecord:
    """
    Create a new participant session using a study token.
    Session persistence is handled by the HTTP layer.
    """
    if not validate_study_token(study_token):
        raise InvalidStudyTokenError("Invalid study token.")

    participant_id = str(uuid.uuid4())
    study_group = assign_study_group(study_token)

    record = ParticipantRecord(participant_id=participant_id, study_group=study_group)
    return record


def validate_study_token(study_token: str) -> bool:
    """
    Validate the provided study token.

    Args:
        study_token (str): The study token to validate.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    # Placeholder logic for token validation
    return len(study_token) > 0


def assign_study_group(study_token: str) -> str:
    """
    Assign a study group based on the study token.

    Args:
        study_token (str): The study token provided by the participant.

    Returns:
        str: The assigned study group label.
    """
    # Placeholder logic for assigning study groups
    return "control" if "control" in study_token.lower() else "experimental"
