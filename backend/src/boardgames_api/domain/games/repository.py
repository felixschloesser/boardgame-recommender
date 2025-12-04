from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql import ColumnElement

from boardgames_api.domain.games.models import BoardgameRecord

# ---------------------------------------------------------------------------
# Filter Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoardgameFilters:
    """
    Query filter specification for boardgame listings.

    q:
        Substring match for title (case-insensitive).
    genre, mechanics, themes:
        Each is a sequence of acceptable string tags.
        Semantics: ANY-of inside each dimension, AND across dimensions.
    """

    q: Optional[str] = None
    genre: Optional[Sequence[str]] = None
    mechanics: Optional[Sequence[str]] = None
    themes: Optional[Sequence[str]] = None


# ---------------------------------------------------------------------------
# Predicate Construction
# ---------------------------------------------------------------------------


def build_predicates(filters: BoardgameFilters) -> list[ColumnElement[bool]]:
    """
    Build SQLAlchemy boolean expressions for the given filters.

    The repository is intentionally dumb: it expresses filter semantics
    directly without embedding domain rules.
    """
    predicates: list[ColumnElement[bool]] = []

    # Title search — parameter-bound substring match
    if filters.q:
        query_term = f"%{filters.q}%"
        predicates.append(BoardgameRecord.title.ilike(query_term))

    # Multi-valued JSON array membership
    for column, values in (
        (BoardgameRecord.genre, filters.genre),
        (BoardgameRecord.mechanics, filters.mechanics),
        (BoardgameRecord.themes, filters.themes),
    ):
        cond = json_array_any(column, values)
        if cond is not None:
            predicates.append(cond)

    return predicates


def json_array_any(
    column, values: Optional[Sequence[str]]
) -> Optional[ColumnElement[bool]]:
    """
    SQLite-correct ANY-membership test for JSON arrays.

    Produces a predicate of the form:
        json_each(column).value IN (values...)

    If values is None or empty, return None (no predicate).
    """
    if not values:
        return None

    # Table-valued function: json_each(column)
    #
    # table_valued("value") exposes a column named "value".
    # This avoids string concatenation or raw SQL fragments.
    je = func.json_each(column).table_valued("value")

    # Values returned by json_each are TEXT;
    # .in_(values) is correct so long as values are strings.
    return je.c.value.in_(list(values))


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
        filters: BoardgameFilters,
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

        predicates = build_predicates(filters)

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
