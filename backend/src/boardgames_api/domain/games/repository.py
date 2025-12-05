from __future__ import annotations

from typing import Any, List, Optional, cast

from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql import ColumnElement

from boardgames_api.domain.games.filters import build_predicates
from boardgames_api.domain.games.records import BoardgameRecord
from boardgames_api.domain.games.schemas import BoardGameResponse

# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class BoardgameRepository:
    """
    Repository responsible for persistence access to BoardgameRecord.

    Still uses SQLAlchemy directly, but cleanly encapsulates:
    - Listing with predicates
    - Count + offset/limit pagination
    - Single-record retrieval
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------
    # Listing
    # ------------------------

    def list(
        self,
        filters: dict | object,
        *,
        limit: int,
        offset: int,
        order_by: ColumnElement[Any] | InstrumentedAttribute[int] | None = None,
    ) -> tuple[int, List[BoardgameRecord]]:
        """
        Return (total_count, page_of_results).

        Parameters:
            filters:   Query filter specification.
            limit:     Maximum number of returned rows.
            offset:    How many rows to skip.
            order_by:  Used for stable ordering; defaults to primary key.

        Notes:
            - Offset–limit pagination is inherently O(n) in the offset.
              For large datasets, keyset pagination is recommended.
        """

        if limit <= 0:
            return 0, []

        order_by = order_by or BoardgameRecord.id

        # Expect filters to be a dict-like with possible keys: q, genre, mechanics, themes
        filt_dict: dict[str, Any] = {}
        if isinstance(filters, dict):
            filt_dict = cast(dict[str, Any], filters)
        else:
            maybe_dict = getattr(filters, "__dict__", {}) or {}
            filt_dict = dict(maybe_dict) if isinstance(maybe_dict, dict) else {}
        predicates = build_predicates(
            q=filt_dict.get("q"),
            genre=filt_dict.get("genre"),
            mechanics=filt_dict.get("mechanics"),
            themes=filt_dict.get("themes"),
        )

        # Base query
        base_query = select(BoardgameRecord)
        if predicates:
            base_query = base_query.where(*predicates)

        # Count via subquery; SQLite handles this well
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = self.session.scalar(count_stmt)
        total = int(total) if total is not None else 0

        if offset >= total:
            return total, []

        rows = self.session.execute(
            base_query.order_by(order_by).offset(offset).limit(limit)
        )
        records = list(rows.scalars())

        return total, records

    # ------------------------
    # Single Fetch
    # ------------------------

    def get(self, record_id: int) -> Optional[BoardgameRecord]:
        """
        Retrieve a single BoardgameRecord by primary key.
        """
        return self.session.get(BoardgameRecord, record_id)

    def list_for_play_context(
        self,
        *,
        players: Optional[int],
        max_minutes: Optional[int],
        limit: int,
    ) -> List[BoardgameRecord]:
        """
        Retrieve records filtered by player count and playing time.
        """
        stmt = select(BoardgameRecord)
        if players is not None:
            stmt = stmt.where(
                BoardgameRecord.min_players <= players,
                BoardgameRecord.max_players >= players,
            )
        if max_minutes is not None:
            stmt = stmt.where(BoardgameRecord.playing_time_minutes <= max_minutes)
        stmt = stmt.order_by(BoardgameRecord.id).limit(limit)
        rows = self.session.execute(stmt)
        return list(rows.scalars())

    # ------------------------
    # Translators
    # ------------------------

    @staticmethod
    def to_response(record: BoardgameRecord) -> BoardGameResponse:
        return BoardGameResponse.from_record(record)


__all__ = ["BoardgameRepository"]
