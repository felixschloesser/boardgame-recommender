from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from boardgames_api.routes.router import router as api_router

app = FastAPI(
    title="Boardgame Recommender API",
    description="An API for recommending board games based on user preferences.",
    version="1.0.0",
)

# Include the API router
app.include_router(api_router)

app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.get("/")
async def root() -> FileResponse:
    """
    Serve the frontend's index.html at the root endpoint.
    """
    return FileResponse("backend/static/index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Lightweight health check without the /api prefix for compatibility with tests.
    """
    return {"status": "ok"}


def main() -> None:
    import uvicorn

    uvicorn.run("boardgames_api.app:app", reload=True)
