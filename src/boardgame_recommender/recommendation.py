from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
import polars as pl

from boardgame_recommender.config import RecommendationConfig
from boardgame_recommender.pipelines.training import Embedding


def _levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous_row = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current_row = [i]
        for j, char_right in enumerate(right, start=1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (char_left != char_right)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _suggestions(target: str, candidates: Sequence[str], limit: int = 3) -> list[str]:
    normalized = [
        (candidate, _levenshtein(target.lower(), candidate.lower()))
        for candidate in candidates
        if isinstance(candidate, str) and candidate
    ]
    ranked = sorted(normalized, key=lambda item: item[1])
    return [name for name, _ in ranked[:limit]]


def _format_missing(names: Sequence[str], catalog: Sequence[str], prefix: str) -> str:
    fragments = []
    for name in names:
        nearest = _suggestions(name, catalog)
        if nearest:
            fragments.append(f"'{name}' (closest: {', '.join(nearest)})")
        else:
            fragments.append(f"'{name}'")
    joined = "; ".join(fragments)
    return f"{prefix}: {joined}"


def _embedding_columns(frame: pl.DataFrame) -> list[str]:
    columns = [column for column in frame.columns if column.startswith("svd_")]
    if not columns:
        raise ValueError("Embedding vectors are missing SVD columns (svd_*)")
    return columns


def _build_preference_vectors(
    liked_matrix: np.ndarray,
    config: RecommendationConfig,
) -> np.ndarray:
    if liked_matrix.size == 0:
        raise ValueError("The liked games could not be mapped to embedding vectors.")
    strategy = config.preferences_vectorization_strategy.lower()
    if strategy == "mixture_of_centroids" and liked_matrix.shape[0] >= config.min_cluster_size:
        cluster_count = min(config.num_centroids, liked_matrix.shape[0])
        if cluster_count < 1:
            return liked_matrix
        if cluster_count == 1:
            return liked_matrix.mean(axis=0, keepdims=True)
        return _run_kmeans(liked_matrix, cluster_count)
    return liked_matrix.mean(axis=0, keepdims=True)


def _run_kmeans(data: np.ndarray, cluster_count: int, iterations: int = 20) -> np.ndarray:
    rng = np.random.default_rng(0)
    centroids = data[rng.choice(data.shape[0], cluster_count, replace=False)]
    for _ in range(iterations):
        distances = np.linalg.norm(data[:, None, :] - centroids[None, :, :], axis=2)
        labels = distances.argmin(axis=1)
        updated = centroids.copy()
        for index in range(cluster_count):
            members = data[labels == index]
            if members.size == 0:
                continue
            updated[index] = members.mean(axis=0)
        if np.allclose(updated, centroids):
            break
        centroids = updated
    return centroids


def _cosine_similarity(
    candidate_matrix: np.ndarray,
    preference_vectors: np.ndarray,
) -> np.ndarray:
    candidate_norms = np.linalg.norm(candidate_matrix, axis=1, keepdims=True)
    candidate_norms[candidate_norms == 0] = 1.0
    preference_norms = np.linalg.norm(preference_vectors, axis=1, keepdims=True)
    preference_norms[preference_norms == 0] = 1.0
    normalized_candidates = candidate_matrix / candidate_norms
    normalized_preferences = preference_vectors / preference_norms
    scores = normalized_candidates @ normalized_preferences.T
    return scores.max(axis=1)


def recommend_games(
    embedding: Embedding,
    liked_games: Sequence[str],
    player_count: int,
    available_time_minutes: int,
    amount: int,
    config: RecommendationConfig,
) -> list[dict[str, Any]]:
    """
    Rank candidate games using cosine similarity between item and preference vectors.
    """

    if not liked_games:
        raise ValueError("Provide at least one liked game to generate recommendations.")

    vectors = embedding.vectors
    if vectors.is_empty():
        return []

    embedding_columns = _embedding_columns(vectors)
    catalog_names = vectors["name"].to_list()
    liked_frame = vectors.filter(pl.col("name").is_in(liked_games))
    if liked_frame.is_empty():
        raise ValueError(
            _format_missing(liked_games, catalog_names, prefix="Liked games not found in catalog")
        )

    present_liked = liked_frame["name"].to_list()
    missing_subset = [name for name in liked_games if name not in present_liked]
    if missing_subset:
        raise ValueError(
            _format_missing(
                missing_subset,
                catalog_names,
                prefix="Some liked games are not part of the trained catalog",
            )
        )

    liked_matrix = liked_frame.select(embedding_columns).to_numpy()
    preference_vectors = _build_preference_vectors(liked_matrix, config)

    playing_time_filter = (
        pl.col("playing_time_minutes").is_null()
        | (pl.col("playing_time_minutes") <= available_time_minutes)
    )
    filtered = vectors.filter(
        (pl.col("min_players") <= player_count)
        & (pl.col("max_players") >= player_count)
        & playing_time_filter
        & (~pl.col("name").is_in(liked_games))
    )
    if filtered.is_empty():
        return []

    candidate_matrix = filtered.select(embedding_columns).to_numpy()
    scores = _cosine_similarity(candidate_matrix, preference_vectors)

    scored = filtered.with_columns(
        pl.Series("score", scores),
    ).sort("score", descending=True).head(amount)

    recommendations: list[dict[str, Any]] = []
    for row in scored.to_dicts():
        playing_time_value = row.get("playing_time_minutes")
        if playing_time_value is None or math.isnan(float(playing_time_value)):
            playing_time = None
        else:
            playing_time = int(playing_time_value)
        recommendations.append(
            {
                "name": row.get("name"),
                "score": float(row.get("score", 0.0)),
                "avg_rating": float(row.get("avg_rating", 0.0)),
                "playing_time": playing_time,
                "min_players": int(row["min_players"]) if row.get("min_players") is not None else None,
                "max_players": int(row["max_players"]) if row.get("max_players") is not None else None,
            }
        )
    return recommendations
