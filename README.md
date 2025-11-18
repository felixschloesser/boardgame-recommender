# Boardgame Recommender

An end-to-end, metadata-only recommender built on BoardGameGeek exports. The CLI
preprocesses raw CSVs, learns a dense vector representation (embedding) that captures similarity patterns in curated
boardgame features, and returns context-aware suggestions for players who know
what they like but not what to try next.

## What’s implemented

- **Dataset curation:** Polars pipelines load `games.csv`, `mechanics.csv`,
  `subcategories.csv`, and `themes.csv`, normalize schemas, and merge auxiliary
  tags.
- **Domain-specific filtering:** configurable guardrails discard stale, obscure,
  or extremely long titles (rating cutoff, popularity quantile, player/time
  bounds).
- **Feature engineering:** description text, mechanics, categories/subcategories,
  and numeric stats (ratings, player counts, complexity, etc.) are tokenized
  with synonym unification, boardgame-domain stopwords, and bi-grams.
- **Boardgame embedding:** weighted TF-IDF + numeric blocks feed a TruncatedSVD model
  (SciPy + scikit-learn) that produces dense `embedding_dimension_<n>` columns stored alongside
  interpretable boardgame metadata in `vectors.parquet`.
- **Recommendation engine:** liked games are clustered into
  groups (KMeans) before cosine similarity scoring, so multiple distinct
  preferences are respected. Candidates are filtered by player count and
  available time before ranking.
- **Workspace tooling:** CLI commands orchestrate preprocessing, training,
  inference, and cleanup. Rich progress logging uses `tqdm` and Python’s logging
  module.

## Repository layout

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

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .          # library + CLI
pip install -e .[dev]     # tooling: pytest, mypy, ruff
```

This project targets Python 3.13+. Dependencies are listed in `pyproject.toml`.

## Data requirements

1. Download the BoardGameGeek dump (e.g. from
   [Kaggle](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/data)).
2. Copy at least the following CSVs into `data/raw/`:
   - `games.csv`
   - `mechanics.csv`
   - `subcategories.csv`
   - `themes.csv`
3. Customize vocabulary helpers if desired:
   - `data/stopwords.txt` — domain stopwords removed from free-text columns.
   - `data/synonyms.toml` — canonical phrases (e.g. “worker-placement”) mapped
     to user-visible variants.

The preprocessing stage fails fast if any required files or columns are missing.

## Configuration overview (`config.toml`)

| Section | Purpose |
| --- | --- |
| `[paths]` | Absolute/relative roots for raw data, processed features, embeddings, and auxiliary word lists. |
| `[preprocessing.filters]` | Guardrails that narrow the catalog (publication year, rating quantile, player count, max play time). |
| `[preprocessing.features]` | Select which columns become `text_*`, `cat_*`, or `num_*` features plus per-column weights. |
| `[preprocessing.tokenization]` | Toggle synonym unification, boardgame stopwords, and the n-gram range used for descriptions. |
| `[training.text_vectorization]` | TF-IDF knobs: min occurrences, max document frequency, and heuristics for long descriptions. |
| `[training.embedding_model]` | Embedding dimensionality + optional normalization of boardgame vectors. |
| `[recommendation]` | Scoring aggregation mode (`max` vs `mean`) and how many preference clusters to form per user query. |

Paths are resolved relative to the config file, so alternative environments can
ship their own TOML file and pass `--config path/to/config.toml`.

## CLI workflow

1. **Preprocess raw CSVs**

   ```bash
   python -m boardgame_recommender preprocess
   ```

   Outputs:
   - `data/processed/boardgames.parquet`
   - `data/processed/data_quality.json` (rows kept, filter counts, timestamp)

2. **Train the embedding model**

   ```bash
   python -m boardgame_recommender train
   ```

   Creates `data/embeddings/<run_id>/` containing `vectors.parquet` + `metadata.json`.

3. **Generate recommendations**

   ```bash
   python -m boardgame_recommender recommend \
       --liked "Risk" "Catan" "Carcassonne" \
       --players 2 \
       --time 40 \
       --amount 8
   ```

   - `--run` lets you pick a specific embedding directory; when omitted, the
     latest completed run is used.
   - `--players` and `--time` define contextual filters applied before scoring.

4. **Clean generated artifacts** (optional)

   ```bash
   python -m boardgame_recommender clean --force
   ```

   Removes `data/processed/` and `data/embeddings/` so you can re-ingest from scratch.

All commands accept `-v/--verbose` (repeat for DEBUG logging) and `-c/--config`
to point at a custom TOML file.

## Development & testing

- Run the entire suite: `pytest`
- Fast unit tests only: `pytest -m "not end_to_end"`
- Pipeline sanity check: `pytest -m end_to_end`
- Static analysis:
  - `ruff check src tests`
  - `mypy --explicit-package-bases src/boardgame_recommender`

Consider installing `pre-commit` hooks so linting, typing, and tests run before
each commit:

```bash
pip install pre-commit
pre-commit install
```

## Future directions

The current focus is a robust metadata-only system. Potential future work:

- ingesting BoardGameGeek rating matrices for collaborative filtering
- hybrid rerankers that combine latent signals with interpretable features
- richer explainability tooling (e.g. SHAP summaries of feature impact)
