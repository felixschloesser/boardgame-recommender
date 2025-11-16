import argparse
import logging
import shutil
from pathlib import Path
from typing import Sequence

from tqdm.auto import tqdm

from boardgame_recommender.config import Config, load_config
from boardgame_recommender.pipelines.preprocessing import preprocess_data
from boardgame_recommender.pipelines.training import train
from boardgame_recommender.recommendation import load_artifacts, recommend_games

LOG_FORMAT = "%(levelname)s [%(name)s] %(message)s"


def _load_configuration(path: str | None) -> Config:
    """Wrapper to load :class:`Config` so it can be patched in tests."""

    return load_config(path)


class TqdmLoggingHandler(logging.Handler):
    """Route log records through tqdm so they don't break progress bars."""

    def __init__(self):
        super().__init__()
        self.terminator = "\n"

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - passthrough
        try:
            msg = self.format(record)
            tqdm.write(msg, end=self.terminator)
        except Exception:
            self.handleError(record)


def _configure_logging(level: str | None) -> None:
    """Configure root logging to play nicely with tqdm progress bars."""

    resolved_level = getattr(logging, (level or "INFO").upper(), logging.INFO)
    handler = TqdmLoggingHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved_level)


def _handle_preprocess_command(arguments: argparse.Namespace) -> None:
    """Entry point for ``preprocess`` CLI subcommand."""

    config_object = getattr(
        arguments, "_configuration_object", None
    ) or _load_configuration(arguments.config_path)
    preprocess_data(
        config_object,
        raw_data_directory_override=Path(arguments.raw_data_directory)
        if arguments.raw_data_directory
        else None,
        output_path_override=Path(arguments.output_path)
        if arguments.output_path
        else None,
        top_record_limit=None,
    )


def _handle_train_command(arguments: argparse.Namespace) -> None:
    """Entry point for ``train`` CLI subcommand."""

    config_object = getattr(
        arguments, "_configuration_object", None
    ) or _load_configuration(arguments.config_path)
    artifacts = train(
        processed_dataset_path=Path(arguments.processed_data_path)
        if arguments.processed_data_path
        else None,
        configuration=config_object,
        output_directory_override=Path(arguments.output_directory)
        if arguments.output_directory
        else None,
        show_progress_bar=not arguments.disable_progress_bar,
    )
    print(f"Training complete. Run identifier: {artifacts.run_identifier}")
    print(
        f"Rows: {artifacts.row_count} | Feature dimension: {artifacts.feature_dimension}"
    )
    if artifacts.evaluation:
        recall = artifacts.evaluation.get("recall_at_10")
        if recall:
            hit_rate = recall.get("hit_rate")
            mean_recall = recall.get("mean_recall")
            queries = int(recall.get("num_queries", 0))
            if hit_rate is not None and mean_recall is not None:
                print(
                    "Recall@10 -> "
                    f"hit_rate={hit_rate:.3f} mean_recall={mean_recall:.3f} "
                    f"queries={queries}"
                )


def _handle_recommend_command(arguments: argparse.Namespace) -> None:
    """Entry point for ``recommend`` CLI subcommand."""

    config_object = getattr(
        arguments, "_configuration_object", None
    ) or _load_configuration(arguments.config_path)
    run_directory, _, catalog, _ = load_artifacts(
        config_object.paths.models_directory, arguments.run_identifier
    )
    if not arguments.liked_games:
        raise SystemExit("--liked requires at least one game name")

    try:
        recommendations = recommend_games(
            catalog_with_embeddings=catalog,
            liked_game_names=arguments.liked_games,
            player_count=arguments.player_count,
            available_time_minutes=arguments.available_time_minutes,
            top_recommendation_count=arguments.top_recommendation_count,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Recommendations from run {run_directory.name}:")
    for recommendation_index, recommendation in enumerate(recommendations, start=1):
        summary = (
            f"{recommendation_index}. {recommendation['name']} "
            f"(score={recommendation['score']:.3f}, rating={recommendation['avg_rating']:.2f}, "
            f"time={recommendation['playing_time']})"
        )
        print(summary)


def _handle_clean_command(arguments: argparse.Namespace) -> None:
    """Entry point for ``clean`` CLI subcommand."""

    config_object = getattr(
        arguments, "_configuration_object", None
    ) or _load_configuration(arguments.config_path)
    processed_features_path = config_object.paths.processed_features
    models_directory = config_object.paths.models_directory

    if processed_features_path.exists():
        processed_features_path.unlink()
    if models_directory.exists():
        shutil.rmtree(models_directory)
    models_directory.mkdir(parents=True, exist_ok=True)
    print("Workspace cleaned.")


def main(argument_values: Sequence[str] | None = None) -> None:
    """CLI bootstrap responsible for parsing args and dispatching subcommands."""

    parser = argparse.ArgumentParser(prog="boardgame_recommender")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preprocess_command = subparsers.add_parser(
        "preprocess",
        help="Build the processed parquet dataset.",
    )
    preprocess_command.add_argument(
        "--config", dest="config_path", help="Path to config.toml", default=None
    )
    preprocess_command.add_argument(
        "--raw-dir",
        dest="raw_data_directory",
        help="Override raw data directory",
        default=None,
    )
    preprocess_command.add_argument(
        "--output",
        dest="output_path",
        help="Override output parquet path",
        default=None,
    )
    preprocess_command.set_defaults(command_handler=_handle_preprocess_command)

    train_command = subparsers.add_parser(
        "train",
        help="Train the recommender pipeline.",
    )
    train_command.add_argument(
        "--config", dest="config_path", help="Path to config.toml", default=None
    )
    train_command.add_argument(
        "--data",
        dest="processed_data_path",
        help="Custom processed parquet path",
        default=None,
    )
    train_command.add_argument(
        "--output",
        dest="output_directory",
        help="Custom models directory",
        default=None,
    )
    train_command.add_argument(
        "--no-progress",
        dest="disable_progress_bar",
        action="store_true",
        help="Disable tqdm progress bar output.",
    )
    train_command.set_defaults(command_handler=_handle_train_command)

    recommend_command = subparsers.add_parser(
        "recommend",
        help="Generate recommendations.",
    )
    recommend_command.add_argument("--config", dest="config_path", default=None)
    recommend_command.add_argument(
        "--run-id",
        dest="run_identifier",
        default=None,
        help="Specific training run to use.",
    )
    recommend_command.add_argument(
        "--liked",
        nargs="+",
        dest="liked_games",
        default=[],
        help="List of liked games (space separated).",
    )
    recommend_command.add_argument(
        "--players",
        dest="player_count",
        type=int,
        required=True,
        help="Minimum amount of players.",
    )
    recommend_command.add_argument(
        "--time",
        dest="available_time_minutes",
        type=int,
        required=True,
        help="Available time in minutes.",
    )
    recommend_command.add_argument(
        "--top-n",
        dest="top_recommendation_count",
        type=int,
        default=5,
        help="Number of desired recommendations.",
    )
    recommend_command.set_defaults(command_handler=_handle_recommend_command)

    clean_command = subparsers.add_parser(
        "clean",
        help="Remove generated artifacts.",
    )
    clean_command.add_argument("--config", dest="config_path", default=None)
    clean_command.set_defaults(command_handler=_handle_clean_command)

    arguments = parser.parse_args(argument_values)

    config_for_logging: Config | None = None
    if hasattr(arguments, "config_path"):
        config_for_logging = _load_configuration(arguments.config_path)
        setattr(arguments, "_configuration_object", config_for_logging)

    log_level = "INFO"
    if config_for_logging is not None and config_for_logging.logging.level:
        log_level = config_for_logging.logging.level

    _configure_logging(log_level)
    arguments.command_handler(arguments)
