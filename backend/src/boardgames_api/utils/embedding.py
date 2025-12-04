from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import polars as pl

DEFAULT_EMBEDDINGS_DIR = (
    Path(__file__).resolve().parents[4] / "data" / "embeddings"
)
DEFAULT_EMBEDDING_RUN = os.getenv("BOARDGAMES_EMBEDDING_RUN")
DEFAULT_EMBEDDINGS_DIR = Path(
    os.getenv("BOARDGAMES_EMBEDDINGS_DIR", DEFAULT_EMBEDDINGS_DIR)
).resolve()


@dataclass
class EmbeddingStore:
    run_identifier: str
    bgg_ids: np.ndarray
    vectors: np.ndarray
    norms: np.ndarray
    names: dict[int, str]

    def has_id(self, bgg_id: int) -> bool:
        return int(bgg_id) in self._index

    def score_candidates(
        self,
        liked_ids: Iterable[int],
        candidate_ids: Iterable[int],
    ) -> dict[int, float]:
        liked_indices = [self._index[i] for i in liked_ids if int(i) in self._index]
        if not liked_indices:
            return {}
        candidate_indices = [self._index[i] for i in candidate_ids if int(i) in self._index]
        if not candidate_indices:
            return {}

        liked_vecs = self.vectors[liked_indices]
        center = liked_vecs.mean(axis=0)
        center_norm = np.linalg.norm(center)
        if not np.isfinite(center_norm) or center_norm == 0.0:
            return {}

        cand_vecs = self.vectors[candidate_indices]
        cand_norms = self.norms[candidate_indices]
        denom = cand_norms * center_norm
        # avoid division by zero
        denom[denom == 0.0] = 1e-12
        scores = cand_vecs.dot(center) / denom

        return {
            int(self.bgg_ids[idx]): float(score)
            for idx, score in zip(candidate_indices, scores)
        }

    def get_name(self, bgg_id: int) -> Optional[str]:
        return self.names.get(int(bgg_id))

    @property
    def _index(self) -> dict[int, int]:
        if not hasattr(self, "__index"):
            self.__index = {int(bgg_id): idx for idx, bgg_id in enumerate(self.bgg_ids)}
        return self.__index


_store: EmbeddingStore | None = None


def _find_latest_run(embeddings_dir: Path) -> Optional[str]:
    if not embeddings_dir.exists():
        return None
    dirs = [entry for entry in embeddings_dir.iterdir() if entry.is_dir()]
    if not dirs:
        return None
    latest = max(dirs, key=lambda p: p.stat().st_mtime)
    return latest.name


def _load_embedding(run_id: Optional[str] = None) -> Optional[EmbeddingStore]:
    embeddings_dir = DEFAULT_EMBEDDINGS_DIR
    run = run_id or DEFAULT_EMBEDDING_RUN or _find_latest_run(embeddings_dir)
    if not run:
        return None
    vectors_path = embeddings_dir / run / "vectors.parquet"
    if not vectors_path.exists():
        return None

    df = pl.read_parquet(vectors_path)
    embed_cols = [col for col in df.columns if col.startswith("embedding_dimension_")]
    if not embed_cols or "bgg_id" not in df.columns:
        return None
    vectors = df.select(embed_cols).to_numpy()
    norms = np.linalg.norm(vectors, axis=1)
    bgg_ids = df["bgg_id"].to_numpy()
    names = (
        df.select(["bgg_id", "name"])
        .to_dict(as_series=False)
        if "name" in df.columns
        else {"bgg_id": [], "name": []}
    )
    name_lookup = {int(i): n for i, n in zip(names.get("bgg_id", []), names.get("name", []))}

    return EmbeddingStore(
        run_identifier=run,
        bgg_ids=bgg_ids,
        vectors=vectors,
        norms=norms,
        names=name_lookup,
    )


def get_embedding_store() -> Optional[EmbeddingStore]:
    global _store
    if _store is not None:
        return _store
    _store = _load_embedding()
    return _store
