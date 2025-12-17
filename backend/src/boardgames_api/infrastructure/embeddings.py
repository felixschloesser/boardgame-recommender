from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl

from boardgames_api.infrastructure import database

DEFAULT_EMBEDDINGS_DIR = Path(__file__).resolve().parents[4] / "data" / "embeddings"
DEFAULT_EMBEDDING_RUN = os.getenv("BOARDGAMES_EMBEDDING_RUN")
DEFAULT_EMBEDDINGS_DIR = Path(
    os.getenv("BOARDGAMES_EMBEDDINGS_DIR", DEFAULT_EMBEDDINGS_DIR)
).resolve()

logger = logging.getLogger("uvicorn.error")
_EMBEDDING_CACHE: dict[str, "Embeddings"] = {}


@dataclass
class Embeddings:
    run_identifier: str
    bgg_ids: np.ndarray
    vectors: np.ndarray
    norms: np.ndarray
    names: dict[int, str]

    def has_id(self, bgg_id: int) -> bool:
        return int(bgg_id) in set(self.bgg_ids.astype(int).tolist())

    def get_name(self, bgg_id: int) -> Optional[str]:
        return self.names.get(int(bgg_id))


def _find_latest_run(embeddings_dir: Path) -> str:
    if not embeddings_dir.exists():
        raise FileNotFoundError(f"Embeddings directory not found: {embeddings_dir}")
    dirs = [entry for entry in embeddings_dir.iterdir() if entry.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"No embedding runs found in {embeddings_dir}")
    latest = max(dirs, key=lambda p: p.stat().st_mtime)
    return latest.name


def load_embedding(run_id: Optional[str] = None, use_cache: bool = True) -> Embeddings:
    cache = _EMBEDDING_CACHE if isinstance(_EMBEDDING_CACHE, dict) else {}
    embeddings_dir = DEFAULT_EMBEDDINGS_DIR
    run = run_id or DEFAULT_EMBEDDING_RUN or _find_latest_run(embeddings_dir)
    if use_cache and run in cache:
        return cache[run]
    vectors_path = embeddings_dir / run / "vectors.parquet"
    if not vectors_path.exists():
        raise FileNotFoundError(f"Embedding vectors not found at {vectors_path}")

    df = pl.read_parquet(vectors_path)
    embed_cols = [col for col in df.columns if col.startswith("embedding_dimension_")]
    if not embed_cols or "bgg_id" not in df.columns:
        raise FileNotFoundError("Embedding parquet missing required columns.")
    vectors = df.select(embed_cols).to_numpy()
    norms = np.linalg.norm(vectors, axis=1)
    bgg_ids = df["bgg_id"].to_numpy()
    names = (
        df.select(["bgg_id", "name"]).to_dict(as_series=False)
        if "name" in df.columns
        else {"bgg_id": [], "name": []}
    )
    name_lookup = {int(i): n for i, n in zip(names.get("bgg_id", []), names.get("name", []))}

    embedding = Embeddings(
        run_identifier=run,
        bgg_ids=bgg_ids,
        vectors=vectors,
        norms=norms,
        names=name_lookup,
    )
    if use_cache:
        cache[run] = embedding
        # keep shared reference in case a test monkeypatched the name
        globals()["_EMBEDDING_CACHE"] = cache
    rows = embedding.bgg_ids.size
    dims = embedding.vectors.shape[1] if embedding.vectors.ndim > 1 else 0
    snapshot = getattr(database, "LAST_DATASET_SNAPSHOT", None)
    dataset_run = snapshot.get("run") if isinstance(snapshot, dict) else None
    dataset_rows = snapshot.get("db_rows") if isinstance(snapshot, dict) else None
    message = "EMBEDDING ready run=%s rows=%d dims=%d" % (run, rows, dims)
    if dataset_run:
        message += " dataset_run=%s" % dataset_run
    if dataset_rows is not None and dataset_rows != rows:
        logger.warning("%s warn=mismatch dataset_rows=%s", message, dataset_rows)
    else:
        logger.info(message)
    return embedding
