from fastapi import APIRouter

from boardgames_api.routes.auth import router as auth_router
from boardgames_api.routes.games import router as games_router
from boardgames_api.routes.recommendations import router as recommendations_router

router = APIRouter(
    prefix="/api",
    tags=["API"],
)

router.include_router(games_router, prefix="/games", tags=["Games"])
router.include_router(recommendations_router, tags=["Recommendations"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "ok"}
