import uuid
from typing import Dict, Optional

# Simulated in-memory storage for sessions
_sessions: Dict[str, Dict[str, Optional[str]]] = {}


def create_session(study_token: str) -> Dict[str, Optional[str]]:
    """
    Create a new participant session using a study token.

    Args:
        study_token (str): The study token provided by the participant.

    Returns:
        dict: A dictionary containing the participant ID and study group.

    Raises:
        ValueError: If the study token is invalid.
    """
    if not validate_study_token(study_token):
        raise ValueError("Invalid study token.")

    participant_id = str(uuid.uuid4())
    study_group = assign_study_group(study_token)

    session = {
        "participant_id": participant_id,
        "study_group": study_group,
    }
    _sessions[participant_id] = session
    return session

def terminate_session(session_id: str) -> None:
    """
    Terminate an existing participant session.

    Args:
        session_id (str): The ID of the session to terminate.

    Raises:
        ValueError: If the session ID is invalid or does not exist.
    """
    if session_id not in _sessions:
        raise ValueError("Session ID not found.")
    del _sessions[session_id]

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

def assign_study_group(study_token: str) -> Optional[str]:
    """
    Assign a study group based on the study token.

    Args:
        study_token (str): The study token provided by the participant.

    Returns:
        Optional[str]: The assigned study group, or None if no group is assigned.
    """
    # Placeholder logic for assigning study groups
    return "control" if "control" in study_token.lower() else "experimental"


def is_valid_session(session_id: Optional[str]) -> bool:
    """
    Check whether the provided session ID exists in the in-memory store.
    """
    return bool(session_id) and session_id in _sessions
