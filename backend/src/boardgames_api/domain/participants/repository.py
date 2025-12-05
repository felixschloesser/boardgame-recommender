from __future__ import annotations

from sqlalchemy.orm import Session

from boardgames_api.domain.participants.records import Participant, ParticipantRecord


class ParticipantRepository:
    """
    Persistence layer for participants.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # CRUD
    def save(self, participant: Participant) -> None:
        record = ParticipantRecord.from_domain(participant)
        self.session.merge(record)
        self.session.commit()

    def get(self, participant_id: str) -> Participant | None:
        record = self.session.get(ParticipantRecord, participant_id)
        if not record:
            return None
        return record.to_domain()
