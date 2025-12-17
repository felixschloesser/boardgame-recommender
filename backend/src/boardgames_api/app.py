import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from boardgames_api.domain.games.bgg_metadata import log_bgg_status
from boardgames_api.domain.recommendations import routes as recommendation_routes
from boardgames_api.http.errors.handlers import register_exception_handlers
from boardgames_api.http.router import router as api_router
from boardgames_api.infrastructure.database import ensure_seeded, init_db
from boardgames_api.infrastructure.embeddings import load_embedding

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR.parent / "static"
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_seeded()
    override = recommendation_routes.OVERRIDE_STUDY_GROUP
    override_raw = recommendation_routes.OVERRIDE_RAW
    if override:
        logger.info("RECOMMENDATION_OVERRIDE active: %s", override.value)
    elif override_raw:
        logger.warning(
            (
                "RECOMMENDATION_OVERRIDE ignored invalid value: %s "
                "(expected 'features' or 'references')"
            ),
            override_raw,
        )
    else:
        logger.info("RECOMMENDATION_OVERRIDE inactive")
    log_bgg_status(logger)
    try:
        load_embedding()
    except Exception as exc:  # pragma: no cover - startup path
        logger.error("Failed to load embeddings at startup: %s", exc)
        raise
    yield


app = FastAPI(
    title="Boardgame Recommender API",
    description="An API for recommending board games based on user preferences.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan,
)

# Include the API router
app.include_router(api_router)

# Cookie-based session support (itsdangerous-signed).
app.add_middleware(
    cast(Any, SessionMiddleware),
    secret_key=os.getenv("SESSION_SECRET_KEY", "dev-session-secret"),
    session_cookie="session_id",
    same_site="lax",
)

# Serve built asset files (JS/CSS/etc.) from Vite's output directory.
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
spa_files = StaticFiles(directory=STATIC_DIR, html=True)

register_exception_handlers(app)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    """
    Serve the favicon for the SPA.
    """
    return FileResponse(STATIC_DIR / "favicon.ico")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """
    Serve the frontend's index.html at the root endpoint.
    """
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "ok"}


@app.middleware("http")
async def spa_fallback(request, call_next):
    """
    Serve the SPA (index.html) for non-API routes while preserving API and health endpoints,
    including proper 405 handling for method mismatches on API routes.
    """
    path = request.url.path
    if (
        path.startswith("/api")
        or path == "/health"
        or path.startswith("/assets")
        or path == "/favicon.ico"
    ):
        return await call_next(request)
    try:
        response = await spa_files.get_response(path=path, scope=request.scope)
    except HTTPException as exc:
        if exc.status_code == 404:
            return FileResponse(STATIC_DIR / "index.html")
        raise
    if response.status_code == 404:
        return FileResponse(STATIC_DIR / "index.html")
    return response


def main() -> None:
    import uvicorn

    uvicorn.run("boardgames_api.app:app", reload=False)


if __name__ == "__main__":
    main()
