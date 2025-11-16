import json
import logging
import math
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import polars as pl

logger = logging.getLogger(__name__)


def _resolve_run_directory(
    artifacts_directory: Path, run_identifier: str | None
) -> Path:
    """Resolve which trained run directory to use for inference."""

    artifacts_directory = Path(artifacts_directory)
    if run_identifier:
        run_directory = artifacts_directory / run_identifier
        if not run_directory.exists():
            raise FileNotFoundError(f"Unknown run id {run_identifier}")
        logger.debug(
            "Using explicit run id %s to reproduce a specific training snapshot",
            run_identifier,
        )
        return run_directory

    latest_symlink = artifacts_directory / "latest"
    if latest_symlink.exists():
        logger.debug("Falling back to latest symlink for freshly trained artifacts")
        return latest_symlink.resolve()
    latest_txt = artifacts_directory / "latest.txt"
    if latest_txt.exists():
        candidate = artifacts_directory / latest_txt.read_text(encoding="utf-8").strip()
        if candidate.exists():
            logger.debug(
                "Latest symlink missing; using textual pointer to preserve last successful run"
            )
            return candidate

    run_directories = sorted(
        [path for path in artifacts_directory.iterdir() if path.is_dir()],
        reverse=True,
    )
    if not run_directories:
        raise FileNotFoundError("No trained runs found.")
    logger.debug("No pointers available; defaulting to most recent run.")
    return run_directories[0]


def load_artifacts(
    models_directory: Path, run_identifier: str | None = None
) -> tuple[Path, dict[str, Any], pl.DataFrame, dict[str, Any]]:
    """Load serialized artifacts (embedding, metadata) for a given run."""

    run_directory = _resolve_run_directory(models_directory, run_identifier)
    logger.debug(
        "Loading inference artifacts from %s to align with preprocessing/training config",
        run_directory,
    )
    bundle = joblib.load(run_directory / "model.pkl")
    catalog = pl.read_parquet(run_directory / "embeddings.parquet")
    metadata_path = run_directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return run_directory, bundle, catalog, metadata


def _levenshtein_distance(left_text: str, right_text: str) -> int:
    """Compute Levenshtein edit distance between two strings."""

    left_text = left_text.lower()
    right_text = right_text.lower()
    if left_text == right_text:
        return 0
    if not left_text:
        return len(right_text)
    if not right_text:
        return len(left_text)

    if len(left_text) < len(right_text):
        left_text, right_text = right_text, left_text

    previous_row = list(range(len(right_text) + 1))
    for row_index, left_character in enumerate(left_text, start=1):
        current_row = [row_index]
        for column_index, right_character in enumerate(right_text, start=1):
            insertions = previous_row[column_index] + 1
            deletions = current_row[column_index - 1] + 1
            substitutions = previous_row[column_index - 1] + (
                left_character != right_character
            )
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _suggest_similar_names(
    target_game_name: str,
    catalog_game_names: Sequence[str],
    maximum_suggestions: int = 3,
) -> list[str]:
    """Suggest catalog names that are closest to the provided target string."""

    distances: list[tuple[int, str]] = []
    for candidate_name in catalog_game_names:
        if candidate_name is None:
            continue
        distance_value = _levenshtein_distance(target_game_name, candidate_name)
        distances.append((distance_value, candidate_name))
    distances.sort(key=lambda item: (item[0], item[1].lower()))
    return [name for _, name in distances[:maximum_suggestions]]


def _format_missing_message(
    missing_names: Sequence[str],
    catalog_game_names: Sequence[str],
    message_prefix: str,
) -> str:
    """Build an actionable error message when liked titles are absent."""

    message_parts = []
    for name in missing_names:
        suggestions = _suggest_similar_names(name, catalog_game_names)
        if suggestions:
            message_parts.append(f"'{name}' (closest match: {', '.join(suggestions)})")
        else:
            message_parts.append(f"'{name}'")
    formatted = "; ".join(message_parts)
    return (
        f"{message_prefix}: {formatted}. "
        "Adjust the inputs or retrain with the desired titles."
    )


def recommend_games(
    catalog_with_embeddings: pl.DataFrame,
    liked_game_names: Sequence[str],
    player_count: int,
    available_time_minutes: int,
    top_recommendation_count: int = 5,
) -> list[dict[str, Any]]:
    """Return top-N recommendations filtered by constraints using k-NN cosine scoring."""

    # Return immediately so the CLI produces an empty list instead of vague errors
    # when the user has not trained the model yet.
    if catalog_with_embeddings.is_empty():
        logger.debug(
            "Catalog is empty; returning no recommendations to avoid misleading blanks"
        )
        return []

    # Only the embedding vectors describe semantic similarity, so isolate the
    # SVD-derived columns regardless of future schema changes.
    embedding_columns = [
        column
        for column in catalog_with_embeddings.columns
        if column.startswith("svd_")
    ]
    # Without embeddings we cannot score neighbors at all, so fail loudly to
    # remind the user to retrain after schema modifications.
    if not embedding_columns:
        raise ValueError("Catalog is missing embedding columns (svd_*)")

    liked_embedding_vectors: np.ndarray | None = None

    def _apply_similarity_scoring(candidate_frame: pl.DataFrame) -> pl.DataFrame:
        # Allow earlier filters to remove all candidates without breaking
        # subsequent logic; downstream code expects a frame in return.
        if candidate_frame.is_empty():
            return candidate_frame

        # When liked games are absent (e.g., validation errors already raised)
        # still produce deterministic zero scores instead of None values.
        if liked_embedding_vectors is None or liked_embedding_vectors.size == 0:
            zero_scores = np.zeros(candidate_frame.height, dtype=float)
            return candidate_frame.with_columns(
                [
                    pl.Series("similarity", zero_scores),
                    pl.Series("score", zero_scores),
                ]
            )

        # Convert to numpy once so we can leverage fast linear algebra for all
        # candidates rather than per-row operations in Polars.
        candidate_matrix = candidate_frame.select(embedding_columns).to_numpy()
        candidate_norms = np.linalg.norm(candidate_matrix, axis=1, keepdims=True)
        candidate_norms[candidate_norms == 0] = 1.0
        liked_norms = np.linalg.norm(liked_embedding_vectors, axis=1)
        liked_norms[liked_norms == 0] = 1.0

        # Cosine similarity gives direction-only proximity, which works well for
        # embedding vectors whose magnitudes may vary between games.
        similarity_matrix = candidate_matrix @ liked_embedding_vectors.T
        similarity_matrix = similarity_matrix / candidate_norms
        similarity_matrix = similarity_matrix / liked_norms[np.newaxis, :]

        # Each candidate only needs its best match among liked games, so collapse
        # the matrix to a single score per row.
        best_neighbor = similarity_matrix.max(axis=1)
        return candidate_frame.with_columns(
            [
                pl.Series("similarity", best_neighbor),
                pl.Series("score", best_neighbor),
            ]
        )

    logger.debug(
        "Applying player/time filters so downstream scoring only considers viable matches"
    )
    # These filters ensure we never recommend games the user cannot play, which
    # keeps the final ranking focused on contextually relevant options.
    filtered_candidates = catalog_with_embeddings.filter(
        (pl.col("min_players") <= player_count)
        & (pl.col("max_players") >= player_count)
        & (pl.col("playing_time_minutes") <= available_time_minutes)
    )
    if filtered_candidates.is_empty():
        logger.debug("No titles satisfy the contextual constraints; exiting early")
        return []

    # Keep the full list of names to build better error messages if a liked
    # title is missing from the catalog.
    catalog_game_names = catalog_with_embeddings["name"].to_list()
    liked_rows = catalog_with_embeddings.filter(pl.col("name").is_in(liked_game_names))
    if liked_rows.is_empty():
        logger.debug(
            "Liked set missing in catalog; surfacing suggestions for user correction"
        )
        message = _format_missing_message(
            liked_game_names,
            catalog_game_names,
            message_prefix="None of the liked games were found",
        )
        raise ValueError(message)

    # Users commonly mistype one of several liked games; fail loudly so they
    # can correct the inputs instead of silently ignoring those titles.
    present_liked_names = set(liked_rows["name"].to_list())
    missing_subset = [
        name for name in liked_game_names if name not in present_liked_names
    ]
    if missing_subset:
        logger.debug(
            "Subset of liked titles not in catalog; forcing failure to avoid silent drops"
        )
        message = _format_missing_message(
            missing_subset,
            catalog_game_names,
            message_prefix="Some liked games are missing from the catalog",
        )
        raise ValueError(message)

    # Extract the liked-game embeddings once so the scoring helper can reuse
    # them for every candidate row.
    liked_embedding_vectors = liked_rows.select(embedding_columns).to_numpy()

    scored_candidates = _apply_similarity_scoring(filtered_candidates)

    # Never surface the original liked games; the purpose is to find adjacent
    # titles, not to echo the input back to the user.
    filtered_candidates = scored_candidates.filter(
        ~pl.col("name").is_in(liked_game_names)
    )
    if filtered_candidates.is_empty():
        logger.debug(
            "All scored candidates overlap with liked games; nothing left to recommend"
        )
        return []

    logger.debug(
        "Ranking %d candidates by cosine similarity and keeping top %d for presentation",
        filtered_candidates.height,
        top_recommendation_count,
    )
    # Present the highest-scoring items first and respect the user-requested
    # limit, mirroring conventional kNN top-k behavior.
    filtered_candidates = filtered_candidates.sort("score", descending=True).head(
        top_recommendation_count
    )

    recommendations: list[dict[str, Any]] = []
    for row in filtered_candidates.to_dicts():
        playing_time_value = row.get("playing_time_minutes")
        if playing_time_value is None:
            playing_time = None
        elif isinstance(playing_time_value, (int, float)) and not math.isnan(
            float(playing_time_value)
        ):
            playing_time = int(playing_time_value)
        else:
            playing_time = None
        recommendations.append(
            {
                "name": row["name"],
                "score": float(row["score"]),
                "similarity": float(row["similarity"]),
                "avg_rating": float(row["avg_rating"]),
                "playing_time": playing_time,
                "min_players": int(row["min_players"])
                if row.get("min_players") is not None
                else None,
                "max_players": int(row["max_players"])
                if row.get("max_players") is not None
                else None,
            }
        )

    return recommendations
