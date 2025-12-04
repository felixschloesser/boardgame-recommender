from typing import List, Optional

from boardgames_api.domain.games.exceptions import GameNotFoundError
from boardgames_api.domain.games.repository import BoardgameFilters, BoardgameRepository
from boardgames_api.domain.games.schemas import BoardGameResponse, PaginatedBoardGamesResponse
from boardgames_api.persistence.database import ensure_seeded, get_session


def get_boardgames(
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
    ensure_seeded()
    with get_session() as session:
        repo = BoardgameRepository(session)
        total, records = repo.list(
            filters=BoardgameFilters(
                q=q,
                genre=genre or [],
                mechanics=mechanics or [],
                themes=themes or [],
            ),
            limit=limit,
            offset=offset,
        )
    paginated_records = records[offset : offset + limit]

    return PaginatedBoardGamesResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[BoardGameResponse.from_record(record) for record in paginated_records],
    )


def get_boardgame_by_id(bgg_id: int) -> BoardGameResponse:
    """
    Retrieve a specific boardgame by its BGG ID.
    """
    sqlite_max_int = 2**63 - 1
    if bgg_id < 1 or bgg_id > sqlite_max_int:
        raise GameNotFoundError("Game not found.")

    ensure_seeded()
    with get_session() as session:
        repo = BoardgameRepository(session)
        record = repo.get(bgg_id)
    if record:
        return BoardGameResponse.from_record(record)

    raise GameNotFoundError("Game not found.")
