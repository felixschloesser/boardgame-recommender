import logging
from datetime import datetime
from typing import Any, Mapping, Optional, cast

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.participants.records import StudyGroup
from boardgames_api.domain.recommendations.models import (
    RecommendationResult,
    RecommendationSelection,
)
from boardgames_api.domain.recommendations.schemas import (
    RecommendationExplanation,
    RecommendationRequest,
)
from boardgames_api.infrastructure.database import Base


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

    @staticmethod
    def _clean_intent(intent: dict[str, object]) -> dict[str, object]:
        cleaned = dict(intent or {})
        for key in (
            "available_time_minutes",
            "player_count",
        ):
            cleaned.pop(key, None)
        return cleaned

    @classmethod
    def from_domain(cls, result: RecommendationResult) -> "RecommendationRecord":
        def _boardgame_payload(boardgame: BoardgameRecord) -> dict[str, object]:
            return {
                "id": boardgame.id,
                "title": boardgame.title,
                "description": boardgame.description,
                "mechanics": boardgame.mechanics,
                "genre": boardgame.genre,
                "themes": boardgame.themes,
                "min_players": boardgame.min_players,
                "max_players": boardgame.max_players,
                "complexity": boardgame.complexity,
                "age_recommendation": boardgame.age_recommendation,
                "num_user_ratings": boardgame.num_user_ratings,
                "avg_user_rating": boardgame.avg_user_rating,
                "year_published": boardgame.year_published,
                "playing_time_minutes": boardgame.playing_time_minutes,
                "image_url": boardgame.image_url,
                "bgg_url": boardgame.bgg_url,
            }

        return cls(
            id=result.id,
            participant_id=result.participant_id,
            created_at=result.created_at.isoformat(),
            model_version=result.model_version,
            experiment_group=result.experiment_group.value,
            intent=result.intent.model_dump(mode="json"),
            recommendations=[
                {
                    "boardgame": _boardgame_payload(sel.boardgame),
                    "explanation": sel.explanation.model_dump(mode="json"),
                }
                for sel in result.selections
            ],
        )

    def to_domain(self) -> Optional[RecommendationResult]:
        try:
            created_at = datetime.fromisoformat(self.created_at)
        except Exception:
            created_at = datetime.now()

        intent_payload = self._clean_intent(dict(self.intent or {}))

        selections: list[RecommendationSelection] = []
        skipped = 0
        for rec_obj in self.recommendations or []:
            if not isinstance(rec_obj, Mapping):
                skipped += 1
                continue
            boardgame_raw_obj = rec_obj.get("boardgame", {})
            explanation_raw_obj = rec_obj.get("explanation", {})
            boardgame_raw: Mapping[str, Any] = (
                cast(Mapping[str, Any], boardgame_raw_obj)
                if isinstance(boardgame_raw_obj, Mapping)
                else {}
            )
            explanation_raw: Mapping[str, Any] = (
                cast(Mapping[str, Any], explanation_raw_obj)
                if isinstance(explanation_raw_obj, Mapping)
                else {}
            )
            explanation = RecommendationExplanation.model_validate(dict(explanation_raw))
            try:
                raw_id = boardgame_raw.get("id")
                if not isinstance(raw_id, (int, str)):
                    raise ValueError("missing boardgame id")
                boardgame = BoardgameRecord(
                    id=int(raw_id),
                    title=str(boardgame_raw.get("title", "")),
                    description=str(boardgame_raw.get("description", "")),
                    mechanics=list(boardgame_raw.get("mechanics") or []),
                    genre=list(boardgame_raw.get("genre") or []),
                    themes=list(boardgame_raw.get("themes") or []),
                    min_players=int(boardgame_raw.get("min_players", 1)),
                    max_players=int(boardgame_raw.get("max_players", 1)),
                    complexity=boardgame_raw.get("complexity"),
                    age_recommendation=boardgame_raw.get("age_recommendation"),
                    num_user_ratings=boardgame_raw.get("num_user_ratings"),
                    avg_user_rating=boardgame_raw.get("avg_user_rating"),
                    year_published=boardgame_raw.get("year_published"),
                    playing_time_minutes=int(
                        boardgame_raw.get("playing_time_minutes", 1)
                    ),
                    image_url=str(boardgame_raw.get("image_url", "")),
                    bgg_url=str(boardgame_raw.get("bgg_url", "")),
                )
            except Exception:
                skipped += 1
                continue
            selections.append(
                RecommendationSelection(
                    boardgame=boardgame,
                    explanation=explanation,
                )
            )
        if skipped:
            logging.getLogger(__name__).debug(
                "Skipped %s invalid recommendation selection rows for %s",
                skipped,
                self.id,
            )

        experiment_group = (
            StudyGroup(self.experiment_group)
            if self.experiment_group in StudyGroup._value2member_map_
            else StudyGroup.REFERENCES
        )

        return RecommendationResult(
            id=self.id,
            participant_id=self.participant_id,
            created_at=created_at,
            intent=RecommendationRequest.model_validate(intent_payload),
            model_version=self.model_version,
            experiment_group=experiment_group,
            selections=selections,
        )


__all__ = ["RecommendationRecord"]
