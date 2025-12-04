from fastapi import APIRouter

from boardgames_api.domain.games.routes import router as games_router
from boardgames_api.domain.participants.routes import router as auth_router
from boardgames_api.domain.recommendations.routes import router as recommendations_router

router = APIRouter(prefix="/api")

router.include_router(games_router, prefix="/games", tags=["Games"])
router.include_router(recommendations_router, tags=["Recommendations"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
