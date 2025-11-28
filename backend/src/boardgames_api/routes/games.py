from typing import Optional

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

from boardgames_api.models.games import BoardGame, Paginated
from boardgames_api.services.games import get_boardgame_by_id, get_boardgames

router = APIRouter()


@router.get("/", response_model=Paginated)
async def list_boardgames(
    request: Request,
    limit: str = Query("10", description="Number of items per page."),
    offset: str = Query("0", description="Offset for pagination."),
    genre: Optional[list[str]] = Query(None, description="Filter by genre."),
    mechanics: Optional[list[str]] = Query(None, description="Filter by mechanics."),
    themes: Optional[list[str]] = Query(None, description="Filter by themes."),
    q: Optional[str] = Query(None, description="Search query for boardgame titles."),
) -> Paginated | JSONResponse:
    """
    List canonical boardgames with optional filters.
    """
    if request.url.path.rstrip("/") not in {"/api/games"}:
        return JSONResponse(status_code=404, content={"detail": "Game not found."})

    try:
        parsed_limit = int(limit)
        parsed_offset = int(offset)
    except (TypeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={
                "title": "Invalid pagination parameters.",
                "status": 400,
                "detail": "limit and offset must be integers.",
            },
        )

    if parsed_limit < 1 or parsed_limit > 100 or parsed_offset < 0:
        return JSONResponse(
            status_code=400,
            content={
                "title": "Invalid pagination parameters.",
                "status": 400,
                "detail": "limit must be 1-100 and offset must be non-negative.",
            },
        )

    return get_boardgames(
        limit=parsed_limit,
        offset=parsed_offset,
        genre=genre,
        mechanics=mechanics,
        themes=themes,
        q=q,
    )


@router.get("/{bgg_id}", response_model=BoardGame)
async def retrieve_boardgame(
    bgg_id: str = Path(..., description="BoardGameGeek ID of the boardgame.")
) -> BoardGame | JSONResponse:
    """
    Retrieve metadata for a specific boardgame by its BGG ID.
    """
    if not bgg_id.isdigit():
        return JSONResponse(status_code=404, content={"detail": "Game not found."})
    numeric_id = int(bgg_id)
    if numeric_id < 1 or numeric_id > 2**31 - 1:
        return JSONResponse(status_code=404, content={"detail": "Game not found."})

    boardgame = get_boardgame_by_id(numeric_id)
    if not boardgame:
        return JSONResponse(status_code=404, content={"detail": "Game not found."})
    return boardgame
