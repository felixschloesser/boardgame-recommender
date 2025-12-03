# Boardgame Recommender CLI

The CLI component of the Boardgame Recommender preprocesses raw data, trains the similarity embedding, and generates recommendations.

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
├─ src/boardgames_cli/
│   ├─ pipelines/             # preprocessing.py + training.py
│   ├─ recommend.py           # liked-game clustering + similarity search
│   ├─ cli.py                 # CLI wiring (`boardgames ...`)
│   └─ app.py                 # entrypoint for `python -m boardgames_cli`
└─ tests/                     # unit + end-to-end coverage
```

## Getting Started

1. **Set up the environment**:
   ```bash
   uv sync                     # installs dependencies into a managed venv
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
   uv run boardgames preprocess
   ```
   - Train the embedding model:
   ```bash
   uv run boardgames train
   ```
   - Generate recommendations:
   ```bash
   uv run boardgames recommend \
       --liked "Risk" "Catan" "Carcassonne" \
       --players 2 \
       --time 40 \
       --amount 8
   ```
   Use `--config path/to/config.toml` with any command to override defaults.

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

- Run the entire suite: `uv run pytest`
- Fast unit tests only: `uv run pytest -m "not end_to_end"`
- Pipeline sanity check: `uv run pytest -m end_to_end`
- Static analysis:
  - `uv run ruff check src tests`
  - `uv run ty backend/src cli/src`

Consider installing `pre-commit` hooks so linting, typing, and tests run before each commit:

```bash
pip install pre-commit
pre-commit install
```

## Future Directions

- Ingesting BoardGameGeek rating matrices for collaborative filtering.
- Hybrid rerankers that combine latent signals with interpretable features.
- Richer explainability tooling (e.g., SHAP summaries of feature impact).
