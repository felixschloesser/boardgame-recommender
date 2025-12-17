import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from sqlalchemy.orm import Session

from boardgames_api.domain.games.bgg_metadata import (
    BggMetadataFetcher,
    fetch_metadata_live,
)
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
        fetcher = BggMetadataFetcher(self.session)
        metadata_map = {}
        selections = result.selections or []
        fetch_enabled = os.getenv("BGG_FETCH_ENABLED", "1").lower() not in {"0", "false", "no"}
        access_token = os.getenv("BGG_ACCESS_TOKEN")
        durations: list[int] = []
        if selections and fetch_enabled and access_token:
            workers = min(8, len(selections))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(fetch_metadata_live, sel.boardgame.id): sel.boardgame.id
                    for sel in selections
                }
                for future in as_completed(future_map):
                    bgg_id = future_map[future]
                    try:
                        metadata, ms = future.result()
                        metadata_map[bgg_id] = metadata
                        if ms is not None:
                            durations.append(ms)
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Parallel BGG fetch failed for %s: %s", bgg_id, exc)
                        metadata_map[bgg_id] = None
            if durations:
                durations_sorted = sorted(durations)
                total = len(durations_sorted)
                slow_count = sum(1 for ms in durations_sorted if ms >= 2000)
                p95_index = max(0, min(total - 1, int(total * 0.95) - 1))
                logger.info(
                    "BGG batch summary rec_id=%s total=%d slow=%d p95_ms=%d max_ms=%d",
                    result.id,
                    total,
                    slow_count,
                    durations_sorted[p95_index] if durations_sorted else 0,
                    durations_sorted[-1] if durations_sorted else 0,
                )

        record = RecommendationRecord(
            id=result.id,
            participant_id=result.participant_id,
            created_at=result.created_at.isoformat(),
            model_version=result.model_version,
            experiment_group=result.experiment_group.value,
            intent=result.intent.model_dump(mode="json"),
            recommendations=[
                {
                    "boardgame": self._payload_with_metadata(
                        fetcher, sel.boardgame, metadata_map.get(sel.boardgame.id)
                    ),
                    "explanation": sel.explanation.model_dump(mode="json"),
                }
                for sel in result.selections
            ],
        )
        self.session.merge(record)
        self.session.commit()

    @staticmethod
    def _payload_with_metadata(fetcher: BggMetadataFetcher, boardgame, metadata_override=None):
        metadata = (
            metadata_override
            if metadata_override is not None
            else fetcher.get(boardgame.id, allow_live_fetch=False)
        )
        description = (
            metadata.description if metadata and metadata.description else boardgame.description
        )
        image_url = metadata.image_url if metadata and metadata.image_url else boardgame.image_url
        return {
            "id": boardgame.id,
            "title": boardgame.title,
            "description": description,
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
            "image_url": image_url,
            "bgg_url": boardgame.bgg_url,
        }

    def get(self, recommendation_id: str) -> Optional[RecommendationResult]:
        """
        Retrieve a persisted recommendation as a domain result.
        """
        record = self.session.get(RecommendationRecord, recommendation_id)
        return record.to_domain() if record else None


__all__ = ["RecommendationRepository"]
