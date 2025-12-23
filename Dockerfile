# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM python:3.12-slim AS python-builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY uv.lock pyproject.toml ./
COPY backend backend

# Replace the baked-in static assets with the latest frontend build before packaging.
COPY --from=frontend-builder /app/backend/src/boardgames_api/static/ backend/src/boardgames_api/static/

# Export runtime requirements for the backend only (excluding the project itself), then install with hashes.
RUN uv export --no-dev --project backend --no-emit-project --output-file requirements.txt && \
    uv pip install --system --no-cache --require-hashes --compile-bytecode -r requirements.txt && \
    uv pip install --system --no-cache --compile-bytecode --no-deps ./backend

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BOARDGAMES_DB_PATH=/app/data/app.sqlite3 \
    BOARDGAMES_PARQUET_PATH=/app/data/processed/boardgames.parquet \
    BOARDGAMES_EMBEDDINGS_DIR=/app/data/embeddings

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r app && useradd -r -g app app

# Bring in the locked, prebuilt Python environment without build tooling.
COPY --from=python-builder /usr/local /usr/local

COPY data data

RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "boardgames_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
