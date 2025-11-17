import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Sequence

import polars as pl
import tomllib

from boardgame_recommender.config import Config, load_config
from boardgame_recommender.pipelines.preprocessing import preprocess_data
from boardgame_recommender.pipelines.training import Embedding, train
from boardgame_recommender.recommend import recommend_games

LOG_FORMAT = "%(levelname)s [%(name)s] %(message)s"
logger = logging.getLogger(__name__)

EMBEDDING_VECORS_FILENAME = "vectors.parquet"
EMBEDDING_METADATA_FILENAME = "metadata.json"


# ----------------------
# IO HELPERS
# ----------------------


def load_stopwords(path: Path) -> set[str]:
    try:
        return {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    except Exception as exc:
        raise SystemExit(f"Failed to load stopwords from {path}: {exc}")


def load_synonyms(path: Path) -> dict[str, list[str]]:
    try:
        data = tomllib.loads(path.read_text("utf-8"))
        return {
            key: values
            for key, values in data.items()
            if (isinstance(values, list) and all(isinstance(v, str) for v in values))
        }
    except Exception as exc:
        raise SystemExit(f"Failed to load synonyms from {path}: {exc}")


def load_features(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise SystemExit(
            "Processed feature dataset not found at "
            f"{path}. Run `python -m boardgame_recommender preprocess` first."
        )

    try:
        return pl.read_parquet(path)
    except Exception as exc:
        raise SystemExit(
            "Failed to load features from "
            f"{path}: {exc}. Try re-running `python -m boardgame_recommender preprocess`."
        )


def load_embedding(path: Path, run_identifier: str) -> Embedding:
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

    vectors_path = run_dir / EMBEDDING_VECORS_FILENAME
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

        vector_path = entry / EMBEDDING_VECORS_FILENAME
        metadata_path = entry / EMBEDDING_METADATA_FILENAME
        if vector_path.exists() and metadata_path.exists():
            candidates.append(entry)

    if not candidates:
        raise SystemExit(
            f"No completed embedding runs found in '{path}'. Train a model first."
        )

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest.name


def _preprocess(config: Config, args: argparse.Namespace) -> None:
    stopwords = load_stopwords(config.paths.stopwords_file)
    synonyms = load_synonyms(config.paths.synonyms_file)

    features, quality_report = preprocess_data(
        directory=config.paths.raw_data_directory,
        stopwords=stopwords,
        synonyms=synonyms,
        config=config.preprocessing,
        show_progress=True,
    )

    out_path = config.paths.processed_features_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features.write_parquet(out_path)

    quality_path = config.paths.data_quality_report_file
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_json = json.dumps(quality_report, indent=2)
    quality_path.write_text(quality_json, encoding="utf-8")

    print(f"Processed feature dataset written to: {out_path}")
    print(f"Data quality report written to: {quality_path}")
    print(f"Rows: {features.height:,}  Columns: {features.width:,}")


def _train(config: Config, args: argparse.Namespace) -> None:
    features = load_features(config.paths.processed_features_file)

    embedding = train(
        features=features,
        config=config,
        show_progress=True,
    )

    run_dir = config.paths.embeddings_directory / embedding.run_identifier
    run_dir.mkdir(parents=True, exist_ok=True)
    vector_path = run_dir / EMBEDDING_VECORS_FILENAME
    embedding.vectors.write_parquet(vector_path)

    metadata_path = run_dir / EMBEDDING_METADATA_FILENAME
    metadata_json = json.dumps(embedding.metadata, indent=2)
    metadata_path.write_text(metadata_json, encoding="utf-8")

    print(f"Trained embedding vectors written to: {vector_path}")
    print(f"Metadata written to: {metadata_path}")
    print(embedding)


def _recommend(config: Config, args: argparse.Namespace) -> None:
    embeddings_dir = config.paths.embeddings_directory
    run_id = args.run_identifier or find_latest_run_identifier(embeddings_dir)

    try:
        embedding = load_embedding(embeddings_dir, run_id)
    except Exception as exc:
        raise SystemExit(f"Failed to load embedding '{run_id}': {exc}")

    recommendations = recommend_games(
        embedding=embedding,
        liked_games=args.liked_games,
        player_count=args.player_count,
        available_time_minutes=args.available_time_minutes,
        amount=args.amount,
        config=config.recommendation,
    )

    if not recommendations:
        print(
            "No games matched your filters; try fewer liked titles or broader time limits."
        )
        return

    # Column width for nice alignment
    name_width = max(len(rec["name"]) for rec in recommendations)

    print("Rank  Name".ljust(name_width + 10) + "Score    Rating    Time")
    print("-" * (name_width + 10 + 25))

    for index, rec in enumerate(recommendations, start=1):
        name = rec.get("name", "<unknown>")
        score = rec.get("score", 0.0)
        rating = rec.get("avg_rating", 0.0)
        time = rec.get("playing_time", "?")

        print(
            f"{index:>4}. {name.ljust(name_width)}  "
            f"{score:>6.3f}   {rating:>6.2f}      {time}"
        )


def _clean(config: Config, args: argparse.Namespace) -> None:
    processed_dir = config.paths.processed_features_directory
    embeddings = config.paths.embeddings_directory

    if not args.force:
        print("This will permanently remove processed features and embeddings.")
        if input("Continue? [y/N]: ").strip().lower() != "y":
            print("Aborted.")
            return

    if processed_dir.exists():
        shutil.rmtree(processed_dir)

    processed_dir.mkdir(parents=True, exist_ok=True)

    if embeddings.exists():
        shutil.rmtree(embeddings)

    embeddings.mkdir(parents=True, exist_ok=True)
    print("Workspace cleaned.")


# ----------------------
# CLI WIRING
# ----------------------


def main(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(prog="boardgame_recommender")

    parser.add_argument(
        "-c",
        "--config",
        default="config.toml",
        help="Path to configuration file.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("preprocess", help="Process raw dataset.")
    p.set_defaults(func=_preprocess)

    t = subparsers.add_parser("train", help="Train the model.")
    t.set_defaults(func=_train)

    r = subparsers.add_parser("recommend", help="Generate recommendations.")
    r.add_argument(
        "--run",
        dest="run_identifier",
        help="Embedding run identifier. Defaults to the latest completed run.",
    )
    r.add_argument("--liked", dest="liked_games", nargs="+", required=True)
    r.add_argument("--players", dest="player_count", type=int, required=True)
    r.add_argument("--time", dest="available_time_minutes", type=int, required=True)
    r.add_argument("--amount", type=int, default=5)
    r.set_defaults(func=_recommend)

    c = subparsers.add_parser("clean", help="Remove generated data.")
    c.add_argument("--force", action="store_true")
    c.set_defaults(func=_clean)

    args = parser.parse_args(argv)

    # logging setup
    level = (
        logging.WARNING
        if args.verbose == 0
        else logging.INFO
        if args.verbose == 1
        else logging.DEBUG
    )
    logging.basicConfig(level=level, format=LOG_FORMAT)

    # load config
    try:
        config = load_config(args.config)
    except Exception as exc:
        raise SystemExit(f"Failed to load config: {exc}")

    try:
        args.func(config, args)
    except Exception as exc:
        logger.error(str(exc))
        raise SystemExit(1)
