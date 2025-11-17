import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Sequence

import polars as pl

from boardgame_recommender.config import Config, load_config
from boardgame_recommender.pipelines.preprocessing import preprocess_data
from boardgame_recommender.pipelines.training import train
from boardgame_recommender.pipelines.features import load_processed_features
from boardgame_recommender.recommendation import load_embedding, recommend_games


LOG_FORMAT = "%(levelname)s [%(name)s] %(message)s"
logger = logging.getLogger(__name__)


# ----------------------
# IO HELPERS
# ----------------------


def load_features(path: Path) -> pl.DataFrame:
    try:
        return pl.read_parquet(path)
    except Exception as exc:
        raise SystemExit(f"Failed to load features from {path}: {exc}")


def load_stopwords(path: Path) -> set[str]:
    try:
        return {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    except Exception as exc:
        raise SystemExit(f"Failed to load stopwords from {path}: {exc}")


# ----------------------
# COMMANDS
# ----------------------


def _preprocess(config: Config, args: argparse.Namespace) -> None:
    domain_stopwords = load_stopwords(config.paths.domain_stopwords_file)
    english_stopwords = load_stopwords(config.paths.english_stopwords_file)
    stopwords = domain_stopwords.union(english_stopwords)

    features = preprocess_data(
        directory=config.paths.raw_data_directory,
        stopwords=stopwords,
        config=config.preprocessing,
    )

    out_path = config.paths.processed_features_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features.write_parquet(out_path)

    print(f"{len(features.columns)} features processed.")


def _train(config: Config, args: argparse.Namespace) -> None:
    features = load_features(config.paths.processed_features_file)

    embedding = train(
        features=features,
        config=config,
        show_progress=config.training.show_progress,
    )

    run_dir = config.paths.embeddings_directory / embedding.run_identifier
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(json.dumps(embedding.metadata, indent=2), encoding="utf-8")

    print(f"Training complete. Run: {embedding.run_identifier}")
    print(f"Rows: {embedding.row_count}  Features: {embedding.feature_dimension}")

    recall = embedding.evaluation.get("recall_at_10", {})
    print(
        "Recall@10 -> "
        f"hit_rate={recall.get('hit_rate', 0):.3f} "
        f"mean_recall={recall.get('mean_recall', 0):.3f} "
        f"queries={int(recall.get('num_queries', 0))}"
    )


def _recommend(config: Config, args: argparse.Namespace) -> None:
    embeddings_dir = config.paths.embeddings_directory
    run_id = args.run_identifier

    try:
        embedding = load_embedding(embeddings_dir, run_id)
    except Exception as exc:
        raise SystemExit(f"Failed to load embedding '{run_id}': {exc}")

    recommendations = recommend_games(
        embedding=embedding,
        liked_game_names=args.liked_games,
        player_count=args.player_count,
        available_time_minutes=args.available_time,
        amount=args.amount,
        config=config.recommendation,
    )

    print(f"Recommendations from run {run_id}:")
    for idx, rec in enumerate(recommendations, start=1):
        print(
            f"- {idx}. {rec['name']} "
            f"(score={rec['score']:.3f}, rating={rec['avg_rating']:.2f}, time={rec['playing_time']})"
        )


def _clean(config: Config, args: argparse.Namespace) -> None:
    processed = config.paths.processed_features_file
    embeddings = config.paths.embeddings_directory

    if not args.force:
        print("This will permanently remove processed features and embeddings.")
        if input("Continue? [y/N]: ").strip().lower() != "y":
            print("Aborted.")
            return

    if processed.exists():
        processed.unlink()

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
    r.add_argument("--run", dest="run_identifier", required=True)
    r.add_argument("--liked", nargs="+", required=True)
    r.add_argument("--players", type=int, required=True)
    r.add_argument("--time", dest="available_time", type=int, required=True)
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
