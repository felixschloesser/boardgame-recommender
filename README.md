# Boardgame Recommender POC

This project is a **proof of concept for an embedding-based boardgame recommender**.
It explores data wrangling, feature engineering and dimensionality reduction applied to BoardGameGeek metadata.

The current system learns **semantic item embeddings from item metadata** (mechanics, categories, descriptions, complexity, etc...) and performs a similarity search to recommend games similar to the ones a user already likes.
Contextual filters (player count, available time) are applied directly on interpretable metadata.


### Embedding Recommender (implemented)

* Uses **only item metadata**; no user rating matrix.
* Creates feature matrices from curated boardgame attributes.
* Applies **Truncated SVD** to obtain low-dimensional semantic embeddings.
* Scores candidates with **k-nearest-neighbor cosine similarity** against each liked title (best-match ranking).
* Returns recommendations satisfying contextual constraints:
  * min players
  * available time


## Possible Improvements

### RandomForest Reranker (not implemented)
I stopped working on the supervised reranker after uncovering a few conceptual issues in my approach.


### Latent-Factor Collaborative Filtering

* Build a **user–item rating matrix** from BGG ratings.
* Apply **SVD** or **NMF** to discover hidden preference dimensions.
* Use resulting latent embeddings for collaborative filtering.
* Combine with learned embeddings for hybrid recommendations.

### Model-Based Explainability

* Use **SHAP** for post-hoc feature importance explanations that justify the RandomForest recommendations.


---

## Tech Stack

* Python 3.13+
* **Polars** for data wrangling and feature stores.
* **Scikit-Learn** for TruncatedSVD and classical ML tooling.
* **argparse** + **tqdm** for ergonomic CLI feedback.
* (Future) SHAP for interpretability of supervised models.

---

## Project Layout

```
├─ data/               # Raw CSVs, processed parquet feature stores and learned embeddings
├─ src/boardgame_recommender/
│   ├─ __main__.py     # allows `python -m boardgame_recommender`
│   ├─ main.py         # CLI wiring + commands
│   ├─ config.py       # Strongly typed TOML loader
│   ├─ pipelines/      # Preprocessing + training stages (embedding-based)
│   └─ recommend.py
```

> Pytest scaffolding is still on the roadmap; the `tests/` package referenced earlier has not been created yet.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

---

## Example Workflow

### 1. Provide BoardGameGeek raw data

Place [BGG CSV exports](https://www.kaggle.com/datasets/threnjen/board-games-database-from-boardgamegeek/data) (`games.csv`, `mechanics.csv`, etc.) into:

```
data/raw/
```

### 2. Preprocess and curate dataset

Configure defaults via `config.toml` (excerpt):

```toml
[paths]
english_stopwords_file = "data/stopwords/english.txt"
domain_stopwords_file = "data/stopwords/boardgame.txt"
raw_data_directory = "data/raw"
processed_features_directory = "data/processed"
embeddings_directory = "data/embeddings"

[logging]
level = "INFO"  # change to "DEBUG" for verbose tracing

[preprocessing]
cutoff_metric = "num_user_ratings"
cutoff_quantile = 0.40

[preprocessing.domain_filters]
enabled = true
min_year = 1995
max_year = 2020
max_min_players = 7
long_play_minutes = 240
long_play_max_minutes = 480
long_play_min_ratings = 1000

[preprocessing.outlier_filtering]
enabled = false                      # optional: opt-in IQR trimming
columns = ["avg_rating", "min_players", "max_players", "playing_time_minutes"]
iqr_multiplier = 1.5                 # adjust whisker sensitivity when enabled

[recommendation]
preferences_vectorization_strategy = "mixture_of_centroids"
num_centroids = 3
```

Preprocessing always runs two guardrails inspired by the [EDA notebook](https://github.com/richengo/Board-Games-Recommender/blob/main/code/01a_Board_Games_EDA_Cleaning.ipynb):

- `[preprocessing.domain_filters]` keeps modern titles (1995–2020 by default), trims niche entries that require more than seven minimum players, and only allows extremely long games (4–8 hours) when they have at least 1k ratings. Tweak or disable this block to widen the candidate pool.
- A light numeric sanity pass enforces hard bounds on the same numeric features (e.g., `min_players` must be between 1 and 20, play time must be < 24h).

Set `[preprocessing.outlier_filtering].enabled = true` only if you want an additional IQR-based trim for the listed columns.

Run preprocessing with:

```bash
python -m boardgame_recommender preprocess
```

This produces the curated feature store (`data/processed/boardgames.parquet`) and a
`data/processed/data_quality.json` snapshot that captures null-counts, numeric
ranges and duplicate tracking for auditing.

### 3. Train the embedding model

```bash
python -m boardgame_recommender train
```

This generates:

* a semantic embedding model (`vectors.parquet`)
* run metadata under `embeddings/<run_identifier>/`

### 4. Request recommendations

```bash
python -m boardgame_recommender recommend \
    --liked "Risk" "Catan" "Carcassonne" \
    --players 2 \
    --time 40
```

### 5. Clean workspace (optional)

```bash
python -m boardgame_recommender clean
```

## Development Workflow

Install dev dependencies and git hooks to guarantee linting, typing, and tests run before every commit:

```bash
pip install -e .[dev] pre-commit
pre-commit install
```

The configured hooks execute `ruff`, `mypy --explicit-package-bases src/boardgame_recommender`, and `pytest`. Use `SKIP=pytest git commit ...` if you need to bypass the full suite temporarily (e.g., when offline), but re-run locally before pushing.
