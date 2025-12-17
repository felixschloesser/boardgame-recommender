from typing import List, Optional

from sqlalchemy.orm import Session

from boardgames_api.domain.games.bgg_metadata import BggMetadataFetcher
from boardgames_api.domain.games.exceptions import GameNotFoundError, GameValidationError
from boardgames_api.domain.games.repository import BoardgameRepository
from boardgames_api.domain.games.schemas import (
    BoardGameResponse,
    PaginatedBoardGamesResponse,
)


def _apply_metadata_overrides(
    response: BoardGameResponse, metadata: object | None
) -> BoardGameResponse:
    """
    Overlay BGG-sourced description/image onto an existing response.
    """
    if metadata is None:
        return response
    description = getattr(metadata, "description", None) or None
    image_url = getattr(metadata, "image_url", None) or None
    updates = {}
    if description:
        updates["description"] = description
    if image_url:
        updates["image_url"] = image_url
    if not updates:
        return response
    return response.model_copy(update=updates)


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
    fetcher = BggMetadataFetcher(db)
    items = [
        _apply_metadata_overrides(
            record.to_response(),
            fetcher.get(record.id, allow_live_fetch=False),
        )
        for record in records
    ]

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
        metadata = BggMetadataFetcher(db).get(bgg_id, allow_live_fetch=True)
        return _apply_metadata_overrides(record.to_response(), metadata)

    raise GameNotFoundError("Game not found.")
