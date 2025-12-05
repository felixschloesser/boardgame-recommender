from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import exists, func, or_, select
from sqlalchemy.sql import ColumnElement

from boardgames_api.domain.games.records import BoardgameRecord


def build_predicates(
    *,
    q: Optional[str] = None,
    genre: Optional[Sequence[str]] = None,
    mechanics: Optional[Sequence[str]] = None,
    themes: Optional[Sequence[str]] = None,
) -> list[ColumnElement[bool]]:
    predicates: list[ColumnElement[bool]] = []

    if q:
        query_term = f"%{q}%"
        predicates.append(BoardgameRecord.title.ilike(query_term))

    for column, values in (
        (BoardgameRecord.genre, genre),
        (BoardgameRecord.mechanics, mechanics),
        (BoardgameRecord.themes, themes),
    ):
        cond = json_array_any_startswith(column, values)
        if cond is not None:
            predicates.append(cond)

    return predicates


def json_array_any_startswith(
    column, values: Optional[Sequence[str]]
) -> Optional[ColumnElement[bool]]:
    if not values:
        return None

    lowered = [str(v).lower() for v in values if str(v).strip()]
    if not lowered:
        return None

    predicates = []
    for val in lowered:
        je = func.json_each(column).table_valued("value")
        predicates.append(
            exists(select(1).select_from(je).where(je.c.value.ilike(f"{val}%")))  # type: ignore[arg-type]
        )
    return or_(*predicates) if predicates else None


__all__ = ["build_predicates", "json_array_any_startswith"]
__all__ = ["build_predicates", "json_array_any_startswith"]
