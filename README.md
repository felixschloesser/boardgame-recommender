# Boardgame Recommender

Boardgame Recommender is an end-to-end system designed to help board game enthusiasts discover new games based on their preferences. By leveraging metadata from BoardGameGeek, the system preprocesses raw data, trains a machine learning model to capture similarity patterns, and provides context-aware recommendations. The project includes a CLI for data preprocessing and model training, a backend web app for serving recommendations, and a frontend for user interaction.

---

## Features

### General
- **End-to-End Workflow**: From raw data ingestion to recommendation delivery.
- **Modular Design**: Separate components for CLI, backend, and frontend.
- **Extensible Configuration**: Easily customize paths, filters, and model parameters.

### CLI
- **Data Preprocessing**: Normalize and curate BoardGameGeek exports.
- **Feature Engineering**: Tokenize text, unify synonyms, and extract numeric features.
- **Model Training**: Generate dense vector embeddings using TF-IDF and TruncatedSVD.
- **Rich Logging**: Progress tracking and detailed reports.

### Backend
- **FastAPI-Based**: A lightweight and efficient backend for serving recommendations.
- **SQLite Integration**: Imports preprocessed data and trained models for querying.
- **RESTful API**: Exposes endpoints for recommendations and metadata.

### Frontend
- **Single Page Application (SPA)**: A React-based interface for user interaction.
- **Dynamic Recommendations**: Query the backend for personalized suggestions.
- **Responsive Design**: Optimized for both desktop and mobile devices.

---

## Repository Layout

```
├── cli/                      # CLI for preprocessing and training
│   ├── README.md             # CLI-specific documentation
│   ├── src/                  # Source code for CLI
│   └── tests/                # Unit tests for CLI
├── backend/                  # Backend web application
│   ├── src/                  # FastAPI application code
│   └── tests/                # Unit and integration tests for backend
├── frontend/                 # Frontend web application
│   ├── src/                  # React application code
│   └── public/               # Static assets
├── data/                     # Data directory
│   ├── raw/                  # Raw BoardGameGeek exports
│   ├── processed/            # Preprocessed features and reports
│   └── embeddings/           # Trained model embeddings
├── pyproject.toml            # Project dependencies and configuration
└── README.md                 # General project documentation
```

---

## Getting Started

### Prerequisites
- Python 3.11–3.14
- Node.js (for frontend development)
- SQLite (for backend database)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/boardgame-recommender.git
   cd boardgame-recommender
   ```

2. Set up the Python environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
   pip install -e '.[dev]'
   ```

3. Set up the frontend:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

4. Run the backend:
   ```bash
   uvicorn backend.src.main:app --reload
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
- Built with React and served by the backend.

---

## Development

### Testing
- Run all tests:
  ```bash
  pytest
  ```
- Lint and type-check:
  ```bash
  ruff check .
  mypy .
  ```

### Pre-commit Hooks
Install pre-commit hooks to ensure code quality:
```bash
pip install pre-commit
pre-commit install
```

---

## Future Directions

- **Collaborative Filtering**: Incorporate user rating matrices.
- **Hybrid Models**: Combine metadata-based and collaborative filtering approaches.
- **Explainability**: Add tools to explain recommendations.
- **Production Deployment**: Optimize for cloud-based deployment.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Support

For questions or issues, please open an issue on GitHub or contact [your email].
