# Boardgame Recommender

Boardgame Recommender is a system designed to help board game enthusiasts discover new games based on their preferences. By leveraging metadata from BoardGameGeek, the system preprocesses raw data, trains a model to capture similarity patterns, and provides context-aware recommendations. The project includes a CLI for data preprocessing and model training, a backend web app for serving recommendations, and a frontend for user interaction.

---

## Features

### CLI
- **Data Preprocessing**: Normalize and curate BoardGameGeek exports.
- **Feature Engineering**: Tokenize text, unify synonyms, and extract numeric features.
- **Model Training**: Generate vector embeddings using TF-IDF and TruncatedSVD.
- **Rich Logging**: Progress tracking and detailed reports.

### Backend
- **FastAPI-Based**: A lightweight and efficient backend for serving recommendations.
- **SQLite Integration**: Imports preprocessed data and trained models for querying.
- **RESTful API**: Exposes endpoints for recommendations and metadata.
- **Live BGG Metadata**: Game detail responses enrich descriptions and cover images from the BoardGameGeek API (enable by providing `BGG_ACCESS_TOKEN`; optional `BGG_FETCH_ENABLED` to force on/off, cache TTL via `BGG_METADATA_TTL_SECONDS`).

### Frontend
- **Single Page Application (SPA)**: A Vue-based user interface.
- **Dynamic Recommendations**: Queries the backend for personalized suggestions.
- **Responsive Design**: Optimized mobile devices.

---

## Repository Layout

```
├── cli/
│   ├── pyproject.toml        # CLI-Project dependencies and configuration
│   ├── config.toml           # Preprocessing and training configuration
│   ├── README.md             # CLI-specific documentation
│   ├── src/                  # Source code for boardgames-cli
│   └── tests/                # Unit and integration tests
│
├── backend/
│   ├── pyproject.toml        # API-Project dependencies and configuration
│   ├── src/                  # Source code for boardgames-api
│   ├── static/               # Served assets, the frontend build output goes here
│   └── tests/                # Unit and integration tests
│
├── frontend/
│   └── src/                  # Vue application code
│
├── data/
│   ├── raw/                  # Raw BoardGameGeek exports
│   ├── processed/            # Preprocessed features and reports
│   ├── embeddings/           # Trained model embeddings
│   ├── stopwords.txt         # Common filler words from the boardgame domain
│   └── synonyms.toml         # Synonyms and spelling variants for normalization
│
├── .gitignore                # Files and directories to be ignored by git
├── .pre-commit-config.yaml   # Automated code quality checks
├── openapi.yaml              # API specification for the backend
├── pyproject.toml            # Workspace definitons (two seperate projects)
├── uv.lock                   # Locked dependencies for reproducible installs
└── README.md                 # General project documentation
```

---

## Getting Started

This repo standardizes on `uv` for Python runtime and dependency management. The workspace-aware resolver keeps the CLI and backend in sync using the checked-in `uv.lock`, and `uv sync` makes installs both reproducible and fast. Install instructions: https://docs.astral.sh/uv/getting-started/installation/

### Prerequisites
- uv (for Python environment and dependency management)
- Node.js (for frontend development)
- SQLite (for backend database)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/felixschloesser/boardgame-recommender.git
   cd boardgame-recommender
   ```

2. Set up the Python environment with uv:
   ```bash
   uv sync --group dev               # installs and locks all workspace deps into .venv
   source .venv/bin/activate         # On Windows: .\.venv\Scripts\activate
   ```

3. Set up the frontend:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

4. Run the backend:
   ```bash
   boardgames-api
   ```

5. Access the application:
   - Open your browser and navigate to `http://127.0.0.1:8000`.

---

## Container Deployment

Build a self-contained image (frontend build + API + datasets) from the repo root:

```bash
podman build -t boardgame-recommender .
```

Run it (adjust host port as needed). Mounting `./data` keeps the SQLite DB and embeddings writable/persistent:

```bash
podman run -d --name boardgames \
  -p 18080:8000 \
  -v $(pwd)/data:/app/data:Z \
  boardgame-recommender \
  uvicorn boardgames_api.app:app --host 0.0.0.0 --port 8000
```

Key environment knobs (already defaulted in the image):
- `BOARDGAMES_DB_PATH=/app/data/app.sqlite3`
- `BOARDGAMES_PARQUET_PATH=/app/data/processed/boardgames.parquet`
- `BOARDGAMES_EMBEDDINGS_DIR=/app/data/embeddings`
- `BGG_ACCESS_TOKEN=<token>` (enable live metadata; omit to stay offline). Optional: `BGG_FETCH_ENABLED` to force on/off.

Health check: `GET /health`. The SPA and API share the same origin; reverse proxies can path-prefix the service without extra config.


---

## Workflow Overview

### CLI
- Preprocess raw data:
  ```bash
  boardgames preprocess
  ```
- Train the model:
  ```bash
  boardgames train embedding
  ```
- Generate recommendations:
  ```bash
  boardgames recommend --liked "Catan" --players 2 --time 40
  ```

### Backend
- Serves the SPA and API endpoints.
- Imports preprocessed data and trained models from `/data`.

### Frontend
- Provides a user-friendly interface for querying recommendations.
- Manages wishlists and liked games.

---

## Development

### Testing
- Run all python tests:
  ```bash
  uv run pytest
  ```
- Lint and type-check:
  ```bash
  uv run ruff check .
  uv run ty backend/src cli/src
  ```

### Pre-commit Hooks
Install pre-commit hooks to ensure code quality:
```bash
uv tool install pre-commit
pre-commit install
```

---

## Future Directions

- **Collaborative Filtering**: Incorporate user rating matrices.
- **Hybrid Models**: Combine metadata-based and collaborative filtering approaches.
- **Explainability**: Add tools to explain recommendations.
- **Production Deployment**: Optimize for container-based deployment.
