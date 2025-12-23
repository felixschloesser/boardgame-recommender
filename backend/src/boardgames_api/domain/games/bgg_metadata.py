from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from boardgamegeek.api import BGGClient
from boardgamegeek.cache import CacheBackendNone
from boardgamegeek.exceptions import BGGApiError, BGGApiTimeoutError, BGGError
from sqlalchemy.orm import Session

from boardgames_api.domain.games.records import BoardgameBggMetadataRecord

# Use uvicorn logger so messages appear in FastAPI server output.
logger = logging.getLogger("uvicorn.error")

BGG_ACCESS_TOKEN = os.getenv("BGG_ACCESS_TOKEN")
_fetch_env = os.getenv("BGG_FETCH_ENABLED")
# Default: enable live fetch only when a token is present; allow explicit override via env.
FETCH_ENABLED = (
    _fetch_env.lower() not in {"0", "false", "no"}
    if _fetch_env is not None
    else bool(BGG_ACCESS_TOKEN)
)
TTL = int(os.getenv("BGG_METADATA_TTL_SECONDS", str(60 * 60 * 24 * 7)))
SLOW_MS = int(os.getenv("BGG_SLOW_MS", "2000"))


@dataclass
class BggMetadata:
    description: Optional[str]
    image_url: Optional[str]
    fetched_at: datetime


def log_bgg_status(startup_logger: logging.Logger) -> None:
    if not FETCH_ENABLED:
        startup_logger.warning(
            "BGG live metadata disabled via BGG_FETCH_ENABLED=0; "
            "serving raw dataset descriptions/images."
        )
    elif not BGG_ACCESS_TOKEN:
        startup_logger.warning(
            "BGG_ACCESS_TOKEN missing; serving raw dataset descriptions/images "
            "without BoardGameGeek enrichment."
        )
    else:
        startup_logger.info("BGG live metadata enabled (TTL=%ss).", TTL)


class BggMetadataFetcher:
    """
    Fetch BGG description/image, cache in SQLite, and return overrides.
    """

    _client: Optional[BGGClient]  # for type checkers

    def __init__(self, session: Session) -> None:
        self.session = session
        self._client: Optional[BGGClient] = None

    # Public API -----------------------------------------------------

    def get(self, bgg_id: int, *, allow_live_fetch: bool = True) -> Optional[BggMetadata]:
        cached = self._load_cached(bgg_id)
        if cached and not self._is_stale(cached):
            return cached

        if not allow_live_fetch or not FETCH_ENABLED or not self._client_available():
            return cached

        fresh = self._fetch_from_bgg(bgg_id)
        if fresh:
            # Skip persistence during live requests to avoid SQLite locks; rely on fresh response.
            return fresh

        return cached

    # Internals ------------------------------------------------------

    def _client_available(self) -> bool:
        if self._client is not None:
            return True
        if not BGG_ACCESS_TOKEN:
            return False
        try:
            self._client = BGGClient(
                access_token=BGG_ACCESS_TOKEN,
                cache=CacheBackendNone(),
                timeout=10,
                retries=1,
                retry_delay=2,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to initialize BGG client: %s", exc)
            return False

    def _load_cached(self, bgg_id: int) -> Optional[BggMetadata]:
        row = self.session.get(BoardgameBggMetadataRecord, bgg_id)
        if not row:
            return None
        return BggMetadata(
            description=row.description or None,
            image_url=row.image_url or None,
            fetched_at=row.fetched_at or datetime.fromtimestamp(0, tz=timezone.utc),
        )

    def _upsert(self, bgg_id: int, metadata: BggMetadata) -> None:
        row = self.session.get(BoardgameBggMetadataRecord, bgg_id)
        if row is None:
            row = BoardgameBggMetadataRecord(
                id=bgg_id,
                description=metadata.description or "",
                image_url=metadata.image_url or "",
                fetched_at=metadata.fetched_at,
            )
            self.session.add(row)
        else:
            row.description = metadata.description or ""
            row.image_url = metadata.image_url or ""
            row.fetched_at = metadata.fetched_at
        self.session.flush()

    def _fetch_from_bgg(self, bgg_id: int) -> Optional[BggMetadata]:
        if not self._client:
            return None
        start = datetime.now(timezone.utc)
        try:
            game = self._client.game(game_id=bgg_id)
        except (BGGApiTimeoutError, BGGApiError):
            elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            logger.warning(
                "BGG fetch failed bgg_id=%s status=timeout ms=%s",
                bgg_id,
                elapsed_ms,
                extra={"bgg_id": bgg_id, "ms": elapsed_ms, "status": "timeout"},
            )
            return None
        except BGGError as exc:
            elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            logger.warning(
                "BGG fetch failed bgg_id=%s status=error ms=%s err=%s",
                bgg_id,
                elapsed_ms,
                exc,
                extra={"bgg_id": bgg_id, "ms": elapsed_ms, "status": "error"},
            )
            return None

        if game is None:
            return None
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        description = (game.description or "").strip()
        image_url = (getattr(game, "image", "") or "").strip()
        if not description and not image_url:
            return None
        log_fn = logger.warning if elapsed_ms >= SLOW_MS else logger.info
        log_fn(
            "BGG fetch ok bgg_id=%s title=%s fields=%s ms=%s slow=%s",
            bgg_id,
            getattr(game, "name", None),
            fields := (
                "description+image"
                if description and image_url
                else "description"
                if description
                else "image"
                if image_url
                else "none"
            ),
            elapsed_ms,
            elapsed_ms >= SLOW_MS,
            extra={
                "bgg_id": bgg_id,
                "title": getattr(game, "name", None),
                "has_description": bool(description),
                "has_image": bool(image_url),
                "fields": fields,
                "ms": elapsed_ms,
                "status": "success",
                "slow": elapsed_ms >= SLOW_MS,
            },
        )

        return BggMetadata(
            description=description or None,
            image_url=image_url or None,
            fetched_at=datetime.now(timezone.utc),
        )

    def _is_stale(self, cached: BggMetadata) -> bool:
        if TTL <= 0:
            return True
        fetched_at = (
            cached.fetched_at.replace(tzinfo=timezone.utc)
            if cached.fetched_at.tzinfo is None
            else cached.fetched_at
        )
        return datetime.now(timezone.utc) - fetched_at > timedelta(seconds=TTL)


def fetch_metadata_live(bgg_id: int) -> tuple[Optional[BggMetadata], Optional[int]]:
    """
    Fetch metadata directly from BGG without touching the cache or shared session.
    Used for parallel fan-out where a shared session/client would cause contention.
    """
    if not FETCH_ENABLED or not BGG_ACCESS_TOKEN:
        return None, None
    start = datetime.now(timezone.utc)
    try:
        client = BGGClient(
            access_token=BGG_ACCESS_TOKEN,
            cache=CacheBackendNone(),
            timeout=10,
            retries=1,
            retry_delay=2,
        )
        game = client.game(game_id=bgg_id)
    except (BGGApiTimeoutError, BGGApiError):
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.warning(
            "BGG fetch failed bgg_id=%s status=timeout ms=%s",
            bgg_id,
            elapsed_ms,
            extra={"bgg_id": bgg_id, "ms": elapsed_ms, "status": "timeout"},
        )
        return None, elapsed_ms
    except BGGError as exc:
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.warning(
            "BGG fetch failed bgg_id=%s status=error ms=%s err=%s",
            bgg_id,
            elapsed_ms,
            exc,
            extra={"bgg_id": bgg_id, "ms": elapsed_ms, "status": "error"},
        )
        return None, elapsed_ms
    except Exception as exc:  # defensive: client init or other errors
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        logger.warning(
            "BGG fetch failed bgg_id=%s status=error ms=%s err=%s",
            bgg_id,
            elapsed_ms,
            exc,
            extra={"bgg_id": bgg_id, "ms": elapsed_ms, "status": "error"},
        )
        return None, elapsed_ms

    if game is None:
        return None, elapsed_ms
    elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    description = (game.description or "").strip()
    image_url = (getattr(game, "image", "") or "").strip()
    if not description and not image_url:
        return None, elapsed_ms
    log_fn = logger.warning if elapsed_ms >= SLOW_MS else logger.info
    log_fn(
        "BGG fetch ok bgg_id=%s title=%s fields=%s ms=%s slow=%s",
        bgg_id,
        getattr(game, "name", None),
        fields := (
            "description+image"
            if description and image_url
            else "description"
            if description
            else "image"
            if image_url
            else "none"
        ),
        elapsed_ms,
        elapsed_ms >= SLOW_MS,
        extra={
            "bgg_id": bgg_id,
            "title": getattr(game, "name", None),
            "has_description": bool(description),
            "has_image": bool(image_url),
            "fields": fields,
            "ms": elapsed_ms,
            "status": "success",
            "slow": elapsed_ms >= SLOW_MS,
        },
    )

    return (
        BggMetadata(
            description=description or None,
            image_url=image_url or None,
            fetched_at=datetime.now(timezone.utc),
        ),
        elapsed_ms,
    )
