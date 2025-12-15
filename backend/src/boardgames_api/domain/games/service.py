from typing import List, Optional

from sqlalchemy.orm import Session

from boardgames_api.domain.games.exceptions import GameNotFoundError, GameValidationError
from boardgames_api.domain.games.repository import BoardgameRepository
from boardgames_api.domain.games.schemas import (
    BoardGameResponse,
    PaginatedBoardGamesResponse,
)


def list_boardgames(
    db: Session,
    limit: int,
    offset: int,
    genre: Optional[List[str]] = None,
    mechanics: Optional[List[str]] = None,
    themes: Optional[List[str]] = None,
    q: Optional[str] = None,
) -> PaginatedBoardGamesResponse:
    """
    Retrieve a paginated list of boardgames with optional filters.
    """
    repo = BoardgameRepository(db)
    total, records = repo.list(
        filters={
            "q": q,
            "genre": genre or [],
            "mechanics": mechanics or [],
            "themes": themes or [],
        },
        limit=limit,
        offset=offset,
    )
    items = [record.to_response() for record in records]

    return PaginatedBoardGamesResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


def get_boardgame(bgg_id: int, db: Session) -> BoardGameResponse:
    """
    Retrieve a specific boardgame by its BGG ID.
    """
    max_sqlite_int = 2**63 - 1
    if bgg_id < 1:
        raise GameValidationError(
            "Path parameter bgg_id must be between 1 and 9223372036854775807."
        )
    if bgg_id > max_sqlite_int:
        raise GameNotFoundError("Game not found.")

    repo = BoardgameRepository(db)
    try:
        record = repo.get(bgg_id)
    except OverflowError as exc:
        raise GameNotFoundError("Game not found.") from exc
    if record:
        return record.to_response()

    raise GameNotFoundError("Game not found.")
