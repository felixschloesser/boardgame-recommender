from dataclasses import dataclass
from typing import Optional


@dataclass
class ParticipantRecord:
    """
    Domain representation of a participant.
    """

    participant_id: str
    study_group: Optional[str] = None
