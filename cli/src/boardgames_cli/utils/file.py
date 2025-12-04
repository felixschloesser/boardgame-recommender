from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path
from typing import Any

import polars as pl

from boardgames_cli.pipelines.training import Embedding

EMBEDDING_VECTORS_FILENAME = "vectors.parquet"
EMBEDDING_METADATA_FILENAME = "metadata.json"


def load_stopwords_from_file(path: Path) -> set[str]:
    try:
        return {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    except Exception as exc:
        raise SystemExit(f"Failed to load stopwords from {path}: {exc}")


def load_synonyms_from_file(path: Path) -> dict[str, list[str]]:
    try:
        data = tomllib.loads(path.read_text("utf-8"))
        return {
            key: values
            for key, values in data.items()
            if isinstance(values, list) and all(isinstance(v, str) for v in values)
        }
    except Exception as exc:
        raise SystemExit(f"Failed to load synonyms from {path}: {exc}")


def load_features_from_file(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise SystemExit(
            "Processed feature dataset not found at "
            f"{path}. Run `boardgames preprocess` first."
        )

    try:
        return pl.read_parquet(path)
    except Exception as exc:
        raise SystemExit(
            "Failed to load features from "
            f"{path}: {exc}. Try re-running `boardgames preprocess`."
        )


def save_processed_features(features: pl.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        features.write_parquet(path)
    except Exception as exc:
        raise SystemExit(f"Failed to write processed features to {path}: {exc}")
    return path


def save_data_quality_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        report_json = json.dumps(report, indent=2)
        path.write_text(report_json, encoding="utf-8")
    except Exception as exc:
        raise SystemExit(f"Failed to write data quality report to {path}: {exc}")
    return path


def save_embedding_run(embedding: Embedding, embeddings_dir: Path) -> tuple[Path, Path]:
    run_dir = embeddings_dir / embedding.run_identifier
    run_dir.mkdir(parents=True, exist_ok=True)

    vectors_path = run_dir / EMBEDDING_VECTORS_FILENAME
    metadata_path = run_dir / EMBEDDING_METADATA_FILENAME

    try:
        embedding.vectors.write_parquet(vectors_path)
    except Exception as exc:
        raise SystemExit(f"Failed to write embedding vectors: {exc}")

    try:
        metadata_json = json.dumps(embedding.metadata, indent=2)
        metadata_path.write_text(metadata_json, encoding="utf-8")
    except Exception as exc:
        raise SystemExit(f"Failed to write embedding metadata: {exc}")

    return vectors_path, metadata_path


def load_embedding_from_file(path: Path, run_identifier: str) -> Embedding:
    """
    Load a trained embedding run from disk.

    Expected directory layout:
        path/
          └── {run_identifier}/
                 ├── vectors.parquet
                 └── metadata.json
    """
    run_dir = path / run_identifier
    if not run_dir.exists():
        raise SystemExit(f"Embedding run '{run_identifier}' not found in {path}")

    vectors_path = run_dir / EMBEDDING_VECTORS_FILENAME
    metadata_path = run_dir / EMBEDDING_METADATA_FILENAME

    try:
        vectors = pl.read_parquet(vectors_path)
    except Exception as exc:
        raise SystemExit(f"Failed to load embedding vectors: {exc}")

    try:
        metadata = json.loads(metadata_path.read_text("utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to load embedding metadata: {exc}")

    return Embedding(
        run_identifier=run_identifier,
        vectors=vectors,
        metadata=metadata,
    )


def find_latest_run_identifier(path: Path) -> str:
    """
    Return the directory name of the most recently modified embedding run.
    """
    if not path.exists():
        raise SystemExit(
            f"Embeddings directory '{path}' does not exist. Train a model first."
        )

    candidates: list[Path] = []
    for entry in path.iterdir():
        if entry.is_symlink():
            continue  # skip helpers like "latest" to avoid stale selections

        if not entry.is_dir():
            continue

        vector_path = entry / EMBEDDING_VECTORS_FILENAME
        metadata_path = entry / EMBEDDING_METADATA_FILENAME
        if vector_path.exists() and metadata_path.exists():
            candidates.append(entry)

    if not candidates:
        raise SystemExit(
            f"No completed embedding runs found in '{path}'. Train a model first."
        )

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest.name


def reset_workspace(processed_dir: Path, embeddings_dir: Path) -> None:
    deleted: list[str] = []
    deleted.extend(_reset_directory(processed_dir))
    deleted.extend(_reset_directory(embeddings_dir))
    db_deleted = _remove_sqlite_db()
    if db_deleted:
        deleted.append(str(db_deleted))

    if deleted:
        print("Removed:")
        for path in deleted:
            print(f" - {path}")
    else:
        print("No artifacts removed.")


def _reset_directory(path: Path) -> list[str]:
    removed: list[str] = []
    if path.exists():
        shutil.rmtree(path)
        removed.append(str(path))
    path.mkdir(parents=True, exist_ok=True)
    return removed


def _remove_sqlite_db() -> str | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        data_dir = parent / "data"
        if data_dir.exists():
            db_path = data_dir / "app.sqlite3"
            if db_path.exists():
                db_path.unlink()
                return str(db_path)
            break
    return None
