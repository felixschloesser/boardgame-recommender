from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from boardgames_api.domain.games.exceptions import GameNotFoundError
from boardgames_api.domain.games.schemas import (
    BoardGameResponse,
    BoardGamesQuery,
    PaginatedBoardGamesResponse,
)
from boardgames_api.domain.games.service import get_boardgame_by_id, get_boardgames
from boardgames_api.http.errors.schemas import ProblemDetailsResponse

router = APIRouter()


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
def list_boardgames(
    query: Annotated[BoardGamesQuery, Depends()],
) -> PaginatedBoardGamesResponse:
    """
    List canonical boardgames with optional filters.
    """
    return get_boardgames(
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
def retrieve_boardgame(
    bgg_id: int,
) -> BoardGameResponse:
    """
    Retrieve metadata for a specific boardgame by its BGG ID.
    """
    try:
        return get_boardgame_by_id(bgg_id)
    except GameNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
