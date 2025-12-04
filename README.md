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
