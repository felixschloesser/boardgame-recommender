import argparse
import logging
from typing import Sequence

from boardgames_cli.config import Config
from boardgames_cli.pipelines.preprocessing import preprocess_data
from boardgames_cli.pipelines.training import Embedding
from boardgames_cli.recommend import recommend_games
from boardgames_cli.utils.file import (
    find_latest_run_identifier,
    load_embedding_from_file,
    load_features_from_file,
    load_stopwords_from_file,
    load_synonyms_from_file,
    reset_workspace,
    save_data_quality_report,
    save_embedding_run,
    save_processed_features,
)

LOG_FORMAT = "%(levelname)s [%(name)s] %(message)s"
logger = logging.getLogger(__name__)


def _preprocess(config: Config, args: argparse.Namespace) -> None:
    stopwords = load_stopwords_from_file(config.paths.stopwords_file)
    synonyms = load_synonyms_from_file(config.paths.synonyms_file)

    features, quality_report = preprocess_data(
        directory=config.paths.raw_data_directory,
        stopwords=stopwords,
        synonyms=synonyms,
        config=config.preprocessing,
        show_progress=True,
    )

    features_path = save_processed_features(
        features, config.paths.processed_features_file
    )
    quality_path = save_data_quality_report(
        quality_report, config.paths.data_quality_report_file
    )

    print(f"Processed feature dataset written to: {features_path}")
    print(f"Data quality report written to: {quality_path}")
    print(f"Rows: {features.height:,}  Columns: {features.width:,}")


def _train(config: Config, args: argparse.Namespace) -> None:
    features = load_features_from_file(config.paths.processed_features_file)

    embedding = Embedding.train(
        features=features,
        config=config,
        show_progress=True,
    )

    vector_path, metadata_path = save_embedding_run(
        embedding, config.paths.embeddings_directory
    )

    print(f"Trained embedding vectors written to: {vector_path}")
    print(f"Metadata written to: {metadata_path}")
    print(embedding)


def _recommend(config: Config, args: argparse.Namespace) -> None:
    embeddings_dir = config.paths.embeddings_directory
    run_id = args.run_identifier or find_latest_run_identifier(embeddings_dir)

    try:
        embedding = load_embedding_from_file(embeddings_dir, run_id)
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

    reset_workspace(processed_dir, embeddings)
    print("Workspace cleaned.")


# ----------------------
# CLI WIRING
# ----------------------
def run(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(prog="boardgames_cli")

    # Global flags
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv).",
    )

    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to configuration file.",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("preprocess", help="Process raw dataset.")
    p.set_defaults(func=_preprocess)

    t = subparsers.add_parser("train", help="Train the model.")
    t.set_defaults(func=_train)

    r = subparsers.add_parser("recommend", help="Generate recommendations.")
    r.add_argument(
        "--run",
        dest="run_identifier",
        help="Embedding run identifier (default: latest run)",
    )
    r.add_argument("--liked", dest="liked_games", nargs="+", required=True)
    r.add_argument("--players", dest="player_count", type=int, required=True)
    r.add_argument("--time", dest="available_time_minutes", type=int, required=True)
    r.add_argument("--amount", type=int, default=5)
    r.set_defaults(func=_recommend)

    c = subparsers.add_parser("clean", help="Remove generated data.")
    c.add_argument("--force", action="store_true")
    c.set_defaults(func=_clean)

    # Parse args
    args = parser.parse_args(argv)

    # Logging
    level = (
        logging.WARNING
        if args.verbose == 0
        else logging.INFO
        if args.verbose == 1
        else logging.DEBUG
    )
    logging.basicConfig(level=level, format=LOG_FORMAT)

    # Config resolution
    if args.config:
        config = Config.load(args.config)
    else:
        config = Config.load_default()

    # Dispatch
    try:
        args.func(config, args)
    except Exception as exc:
        logger.error(str(exc))
        raise SystemExit(1)
