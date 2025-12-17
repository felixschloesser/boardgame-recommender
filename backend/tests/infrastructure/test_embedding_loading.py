from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from boardgames_api.domain.recommendations.reccomender import (
    AggregationStrategy,
    EmbeddingSimilarityRecommender,
)
from boardgames_api.infrastructure import embeddings as embedding


@pytest.fixture(autouse=True)
def reset_store(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(embedding, "_EMBEDDING_CACHE", None, raising=False)
    monkeypatch.setattr(embedding, "DEFAULT_EMBEDDINGS_DIR", tmp_path)


def test_load_embedding_raises_when_missing(monkeypatch, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        embedding.load_embedding(use_cache=False)


def test_get_embedding_store_loads_valid_vectors(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    df = pl.DataFrame(
        {
            "bgg_id": [1, 2],
            "name": ["Alpha", "Beta"],
            "embedding_dimension_0": [1.0, 0.0],
            "embedding_dimension_1": [0.0, 1.0],
        }
    )
    (run_dir / "vectors.parquet").parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(run_dir / "vectors.parquet")

    store = embedding.load_embedding(use_cache=False)
    assert store is not None
    assert store.run_identifier == "run1"
    assert store.has_id(1)
    assert store.get_name(1) == "Alpha"
    recommender = EmbeddingSimilarityRecommender(aggregation=AggregationStrategy.MAX)
    # Patch loader so the recommender uses our in-memory store.
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.reccomender.load_embedding", lambda: store
    )
    ranked = recommender.recommend(liked_games=[1], num_results=1)
    assert ranked
    assert ranked[0].bgg_id == 2
