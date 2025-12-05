import logging
from typing import Optional

from sqlalchemy.orm import Session

from boardgames_api.domain.recommendations.models import (
    RecommendationResult,
)
from boardgames_api.domain.recommendations.records import RecommendationRecord

logger = logging.getLogger(__name__)


class RecommendationRepository:
    """
    Persistence adapter for recommendation results.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, result: RecommendationResult) -> None:
        """
        Persist a domain recommendation result.
        """
        record = RecommendationRecord(
            id=result.id,
            participant_id=result.participant_id,
            created_at=result.created_at.isoformat(),
            model_version=result.model_version,
            experiment_group=result.experiment_group.value,
            intent=result.intent.model_dump(mode="json"),
            recommendations=[
                {
                    "boardgame": {
                        "id": sel.boardgame.id,
                        "title": sel.boardgame.title,
                        "description": sel.boardgame.description,
                        "mechanics": sel.boardgame.mechanics,
                        "genre": sel.boardgame.genre,
                        "themes": sel.boardgame.themes,
                        "min_players": sel.boardgame.min_players,
                        "max_players": sel.boardgame.max_players,
                        "complexity": sel.boardgame.complexity,
                        "age_recommendation": sel.boardgame.age_recommendation,
                        "num_user_ratings": sel.boardgame.num_user_ratings,
                        "avg_user_rating": sel.boardgame.avg_user_rating,
                        "year_published": sel.boardgame.year_published,
                        "playing_time_minutes": sel.boardgame.playing_time_minutes,
                        "image_url": sel.boardgame.image_url,
                        "bgg_url": sel.boardgame.bgg_url,
                    },
                    "explanation": sel.explanation.model_dump(mode="json"),
                }
                for sel in result.selections
            ],
        )
        self.session.merge(record)
        self.session.commit()

    def get(self, recommendation_id: str) -> Optional[RecommendationResult]:
        """
        Retrieve a persisted recommendation as a domain result.
        """
        record = self.session.get(RecommendationRecord, recommendation_id)
        return record.to_domain() if record else None


__all__ = ["RecommendationRepository"]
