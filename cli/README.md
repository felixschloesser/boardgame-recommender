# Boardgame Recommender CLI

The CLI component of the Boardgame Recommender is responsible for preprocessing raw data, training the recommendation model, and generating embeddings. It is designed to handle the data pipeline and model preparation, which are later used by the web application for serving recommendations.

## Features

- **Dataset Curation**: Load and normalize BoardGameGeek CSV exports.
- **Domain-Specific Filtering**: Discard stale, obscure, or overly long titles.
- **Feature Engineering**: Tokenize text, unify synonyms, and extract numeric features.
- **Boardgame Embedding**: Generate dense vector representations using TF-IDF and TruncatedSVD.
- **CLI Tooling**: Orchestrate preprocessing, training, inference, and cleanup with rich logging.

## Repository Layout

```
├─ config.toml                # Default configuration (paths + hyper-parameters)
├─ data/
│   ├─ raw/                   # Place BGG CSV exports here
│   ├─ processed/             # Generated features + quality reports
│   └─ embeddings/            # One directory per trained run
├─ src/boardgame_recommender/
│   ├─ pipelines/             # preprocessing.py + training.py
│   ├─ recommend.py           # liked-game clustering + similarity search
│   ├─ main.py                # CLI wiring (`python -m boardgame_recommender...`)
│   └─ config.py              # TOML-file loader
└─ tests/                     # unit + end-to-end coverage
```

## Getting Started

1. **Set up the environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
   pip install -e '.'          # Library + CLI
   pip install -e '.[dev]'     # Development tools (pytest, mypy, ruff)
   ```

2. **Prepare the data**:
   - Download the BoardGameGeek dump (e.g., from [Kaggle](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/data)).
   - Copy the following CSVs into `data/raw/`:
     - `games.csv`
     - `mechanics.csv`
     - `subcategories.csv`
     - `themes.csv`

3. **Run CLI commands**:
   - Preprocess raw CSVs:
     ```bash
     python -m boardgame_recommender preprocess
     ```
   - Train the embedding model:
     ```bash
     python -m boardgame_recommender train
     ```
   - Generate recommendations:
     ```bash
     python -m boardgame_recommender recommend \
         --liked "Risk" "Catan" "Carcassonne" \
         --players 2 \
         --time 40 \
         --amount 8
     ```

## Configuration Overview (`config.toml`)

| Section | Purpose |
| --- | --- |
| `[paths]` | Absolute/relative roots for raw data, processed features, embeddings, and auxiliary word lists. |
| `[preprocessing.filters]` | Guardrails that narrow the catalog (publication year, rating quantile, player count, max play time). |
| `[preprocessing.features]` | Select which columns become `text_*`, `cat_*`, or `num_*` features plus per-column weights. |
| `[preprocessing.tokenization]` | Toggle synonym unification, boardgame stopwords, and the n-gram range used for descriptions. |
| `[training.text_vectorization]` | TF-IDF knobs: min occurrences, max document frequency, and heuristics for long descriptions. |
| `[training.embedding_model]` | Embedding dimensionality + optional normalization of boardgame vectors. |
| `[recommendation]` | Scoring aggregation mode (`max` vs `mean`) and how many preference clusters to form per user query. |

Paths are resolved relative to the config file, so alternative environments can ship their own TOML file and pass `--config path/to/config.toml`.

## Development & Testing

- Run the entire suite: `pytest`
- Fast unit tests only: `pytest -m "not end_to_end"`
- Pipeline sanity check: `pytest -m end_to_end`
- Static analysis:
  - `ruff check src tests`
  - `mypy --explicit-package-bases src/boardgame_recommender`

Consider installing `pre-commit` hooks so linting, typing, and tests run before each commit:

```bash
pip install pre-commit
pre-commit install
```

## Future Directions

- Ingesting BoardGameGeek rating matrices for collaborative filtering.
- Hybrid rerankers that combine latent signals with interpretable features.
- Richer explainability tooling (e.g., SHAP summaries of feature impact).