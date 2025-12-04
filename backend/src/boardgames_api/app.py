import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from boardgames_api.http.errors.handlers import register_exception_handlers
from boardgames_api.http.router import router as api_router
from boardgames_api.persistence.database import ensure_seeded, init_db

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_seeded()
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

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

register_exception_handlers(app)


@app.get("/")
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


def main() -> None:
    import uvicorn

    uvicorn.run("boardgames_api.app:app", reload=False)


if __name__ == "__main__":
    main()
