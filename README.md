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
│   ├─ cli.py          # python -m boardgame_recommender entrypoint
│   ├─ config.py       # Strongly typed TOML loader
│   ├─ pipelines/      # Preprocessing + training stages (embedding-based)
│   └─ recommendation.py
└─ tests/              # Pytest suites + fixtures (incl. end-to-end test)
```

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

Configure defaults via `config.toml`:

```toml
[logging]
level = "INFO"  # change to "DEBUG" for verbose tracing

[preprocessing]
top_n = 2000
```

Run preprocessing with:

```bash
python -m boardgame_recommender preprocess
```

### 3. Train the embedding model

```bash
python -m boardgame_recommender train
```

This generates:

* a semantic embedding catalog
* a serialized model bundle
* run metadata under `models/<run_identifier>/`

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
