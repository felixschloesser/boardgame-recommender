from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from boardgames_api.domain.games.schemas import BoardGameResponse
from boardgames_api.infrastructure.database import Base


class BoardgameRecord(Base):
    __tablename__ = "boardgames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)

    description: Mapped[str] = mapped_column(Text, default="")

    mechanics: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    genre: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)
    themes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list)

    min_players: Mapped[int] = mapped_column(Integer)
    max_players: Mapped[int] = mapped_column(Integer)

    complexity: Mapped[Optional[float]] = mapped_column(Float)

    age_recommendation: Mapped[Optional[int]] = mapped_column(Integer)
    num_user_ratings: Mapped[Optional[int]] = mapped_column(Integer)
    year_published: Mapped[Optional[int]] = mapped_column(Integer)

    avg_user_rating: Mapped[Optional[float]] = mapped_column(Float)

    playing_time_minutes: Mapped[int] = mapped_column(Integer)

    image_url: Mapped[str] = mapped_column(String, default="")
    bgg_url: Mapped[str] = mapped_column(String, default="")

    def to_response(self) -> BoardGameResponse:
        return BoardGameResponse.from_record(self)


__all__ = ["BoardgameRecord"]
