from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from boardgames_api.persistence.database import Base


class RecommendationRecord(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    participant_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    experiment_group: Mapped[str] = mapped_column(String, nullable=False)
    intent: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    recommendations: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False
    )
