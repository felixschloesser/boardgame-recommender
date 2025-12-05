from typing import List, Optional

from sqlalchemy.orm import Session

from boardgames_api.domain.games.exceptions import GameNotFoundError
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
    repo = BoardgameRepository(db)
    record = repo.get(bgg_id)
    if record:
        return record.to_response()

    raise GameNotFoundError("Game not found.")
