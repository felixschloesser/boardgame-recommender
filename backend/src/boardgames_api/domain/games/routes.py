from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query

from boardgames_api.domain.games.schemas import (
    BoardGameResponse,
    BoardGamesQuery,
    PaginatedBoardGamesResponse,
)
from boardgames_api.domain.games.service import get_boardgame, list_boardgames
from boardgames_api.http.dependencies import db_session
from boardgames_api.http.errors.schemas import ProblemDetailsResponse

router = APIRouter()


def _build_boardgames_query(
    limit: int = Query(default=10, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    genre: Optional[List[str]] = Query(
        default=None, description="Filter by genre", alias="genre"
    ),
    mechanics: Optional[List[str]] = Query(
        default=None, description="Filter by mechanic", alias="mechanics"
    ),
    themes: Optional[List[str]] = Query(
        default=None, description="Filter by theme", alias="themes"
    ),
    q: Optional[str] = Query(default=None, description="Full-text search"),
) -> BoardGamesQuery:
    """
    Dependency to map query parameters into a BoardGamesQuery model.
    """
    return BoardGamesQuery(
        limit=limit,
        offset=offset,
        genre=genre,
        mechanics=mechanics,
        themes=themes,
        q=q,
    )


@router.get(
    "/",
    response_model=PaginatedBoardGamesResponse,
    responses={
        400: {
            "model": ProblemDetailsResponse,
            "description": "Invalid pagination parameters.",
        }
    },
)
def list_games(
    query: Annotated[BoardGamesQuery, Depends(_build_boardgames_query)],
    db=Depends(db_session),
) -> PaginatedBoardGamesResponse:
    """
    List canonical boardgames with optional filters.
    """
    return list_boardgames(
        db=db,
        limit=query.limit,
        offset=query.offset,
        genre=query.genre,
        mechanics=query.mechanics,
        themes=query.themes,
        q=query.q,
    )


@router.get(
    "/{bgg_id}",
    response_model=BoardGameResponse,
    responses={404: {"model": ProblemDetailsResponse, "description": "Game not found."}},
)
def get_game(
    bgg_id: int,
    db=Depends(db_session),
) -> BoardGameResponse:
    """
    Retrieve metadata for a specific boardgame by its BGG ID.
    """
    return get_boardgame(bgg_id, db=db)
