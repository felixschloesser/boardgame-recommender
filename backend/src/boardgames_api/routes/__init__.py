# This package contains the API route handlers for the FastAPI application.
# Each module corresponds to a specific feature area (e.g., auth, games, recommendations).

from fastapi import APIRouter

from .auth import router as auth_router
from .games import router as games_router
from .recommendations import router as recommendations_router

# Create a master router to include all feature-specific routers
api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(games_router, prefix="/games", tags=["games"])
api_router.include_router(
    recommendations_router, prefix="/recommendation", tags=["recommendations"]
)
