from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from boardgames_api.utils import embedding


@pytest.fixture(autouse=True)
def reset_store(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(embedding, "_store", None, raising=False)
    monkeypatch.setattr(embedding, "DEFAULT_EMBEDDINGS_DIR", tmp_path)


def test_get_embedding_store_returns_none_when_missing(monkeypatch, tmp_path: Path) -> None:
    store = embedding.get_embedding_store()
    assert store is None


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

    store = embedding.get_embedding_store()
    assert store is not None
    assert store.run_identifier == "run1"
    assert store.has_id(1)
    assert store.get_name(1) == "Alpha"
    scores = store.score_candidates(liked_ids=[1], candidate_ids=[2])
    assert scores
