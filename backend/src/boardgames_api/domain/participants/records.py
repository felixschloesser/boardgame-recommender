from dataclasses import dataclass
from enum import Enum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from boardgames_api.infrastructure.database import Base


class StudyGroup(str, Enum):
    FEATURES = "features"
    REFERENCES = "references"


class ParticipantRecord(Base):
    """
    Persistence model for participants.
    """

    __tablename__ = "participants"

    participant_id: Mapped[str] = mapped_column(String, primary_key=True)
    study_group: Mapped[str] = mapped_column(String, nullable=False)

    @classmethod
    def from_domain(cls, participant: "Participant") -> "ParticipantRecord":
        return cls(
            participant_id=participant.participant_id,
            study_group=participant.study_group.value,
        )

    def to_domain(self) -> "Participant":
        return Participant(
            participant_id=self.participant_id,
            study_group=StudyGroup(self.study_group),
        )

@dataclass(frozen=True)
class Participant:
    participant_id: str
    study_group: StudyGroup


__all__ = ["ParticipantRecord", "Participant", "StudyGroup"]
