from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence, cast

import numpy as np
import polars as pl
from numpy.typing import NDArray
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from boardgame_recommender.config import RecommendationConfig
from boardgame_recommender.pipelines.training import Embedding
from boardgame_recommender.utils.transforms import normalize_rows
from boardgame_recommender.utils.validation import format_missing

_TASTE_PREFIX = "taste_"
Array = NDArray[np.float64]


def recommend_games(
    *,
    embedding: Embedding,
    liked_games: Sequence[str],
    player_count: int,
    available_time_minutes: int,
    amount: int,
    config: RecommendationConfig,
) -> list[dict[str, Any]]:
    """
    Recommend games based on a trained embedding and a set of liked games.
    """
    context = RecommendationContext.from_embedding(embedding, config)
    context.validate_query(
        liked_games=liked_games,
        player_count=player_count,
        available_time_minutes=available_time_minutes,
        amount=amount,
    )

    liked_frame = context.locate_liked_rows(liked_games)
    liked_matrix = cast(
        Array,
        liked_frame.select(context.embedding_columns)
        .to_numpy()
        .astype(np.float64, copy=False),
    )

    taste_vectors = context.build_taste_vectors(liked_matrix)

    candidate_frame = context.select_candidates(
        liked_games=liked_games,
        player_count=player_count,
        available_time_minutes=available_time_minutes,
    )
    if candidate_frame.is_empty():
        return []

    candidate_matrix = cast(
        Array,
        candidate_frame.select(context.embedding_columns)
        .to_numpy()
        .astype(np.float64, copy=False),
    )
    similarity_matrix = _cosine_similarity(candidate_matrix, taste_vectors)
    scores = _aggregate_scores(similarity_matrix, strategy=config.similarity_aggregation)

    ranked = (
        candidate_frame.with_columns(pl.Series("score", scores))
        .sort("score", descending=True)
        .head(amount)
    )

    return [_format_result_row(row) for row in ranked.to_dicts()]


@dataclass
class RecommendationContext:
    embedding: Embedding
    config: RecommendationConfig
    embedding_columns: list[str]

    @classmethod
    def from_embedding(
        cls,
        embedding: Embedding,
        config: RecommendationConfig,
    ) -> RecommendationContext:
        vectors = embedding.vectors
        if vectors.is_empty():
            raise ValueError("Embedding contains no rows; train the model first.")

        metadata_columns = embedding.metadata.get("embedding_columns") or []
        discovered_columns = [
            column for column in vectors.columns if column.startswith(_TASTE_PREFIX)
        ]

        if metadata_columns:
            missing = [column for column in metadata_columns if column not in discovered_columns]
            if missing:
                raise ValueError(
                    "Embedding metadata expects columns "
                    f"{missing}, but they are missing from vectors."
                )
            embedding_columns = list(metadata_columns)
        else:
            if not discovered_columns:
                raise ValueError("Embedding vectors do not contain any taste_* columns.")
            embedding_columns = discovered_columns

        return cls(
            embedding=embedding,
            config=config,
            embedding_columns=embedding_columns,
        )

    def validate_query(
        self,
        liked_games: Sequence[str],
        player_count: int,
        available_time_minutes: int,
        amount: int,
    ) -> None:
        if not liked_games:
            raise ValueError("Provide at least one liked game to anchor recommendations.")
        if player_count <= 0:
            raise ValueError("player_count must be positive.")
        if available_time_minutes <= 0:
            raise ValueError("available_time_minutes must be positive.")
        if amount <= 0:
            raise ValueError("amount must be positive.")

    def locate_liked_rows(self, liked_games: Sequence[str]) -> pl.DataFrame:
        frame = self.embedding.vectors
        liked_frame = frame.filter(pl.col("name").is_in(liked_games))
        if liked_frame.is_empty():
            catalog = frame["name"].to_list()
            raise ValueError(
                format_missing(liked_games, catalog, prefix="Liked games not found")
            )

        present = set(liked_frame["name"].to_list())
        missing = [name for name in liked_games if name not in present]
        if missing:
            catalog = frame["name"].to_list()
            raise ValueError(format_missing(missing, catalog, prefix="Missing liked games"))
        return liked_frame

    def select_candidates(
        self,
        *,
        liked_games: Sequence[str],
        player_count: int,
        available_time_minutes: int,
    ) -> pl.DataFrame:
        vectors = self.embedding.vectors

        player_fit = (
            pl.col("min_players").is_not_null()
            & pl.col("max_players").is_not_null()
            & (pl.col("min_players") <= player_count)
            & (pl.col("max_players") >= player_count)
        )
        time_fit = (
            pl.col("playing_time_minutes").is_not_null()
            & (pl.col("playing_time_minutes") <= available_time_minutes)
        )

        return vectors.filter(
            player_fit
            & time_fit
            & (~pl.col("name").is_in(liked_games))
        )

    def build_taste_vectors(self, liked_matrix: Array) -> Array:
        if liked_matrix.size == 0:
            raise ValueError("Liked games could not be mapped to the embedding space.")
        taste_config = self.config.taste_model

        liked_count = liked_matrix.shape[0]
        centroid_count = _determine_centroid_count(
            liked_count=liked_count,
            min_samples_per_centroid=taste_config.min_samples_per_centroid,
            dynamic_centroids=taste_config.dynamic_centroids,
            centroid_scaling_factor=taste_config.centroid_scaling_factor,
        )

        if centroid_count == 1 or liked_count <= centroid_count:
            taste_vectors = cast(Array, liked_matrix.mean(axis=0, keepdims=True))
        else:
            safe_centroids = max(1, min(centroid_count, max(1, liked_count // 2)))
            taste_vectors = _run_kmeans(
                liked_matrix,
                n_clusters=safe_centroids,
                random_state=self.config.random_seed,
            )

        return normalize_rows(taste_vectors)


def _cosine_similarity(
    candidates: Array,
    tastes: Array,
) -> Array:
    if candidates.size == 0 or tastes.size == 0:
        empty = np.zeros((candidates.shape[0], tastes.shape[0]), dtype=np.float64)
        return cast(Array, empty)
    return cast(Array, cosine_similarity(candidates, tastes))


def _aggregate_scores(similarity: Array, strategy: str) -> Array:
    if similarity.size == 0:
        return cast(Array, np.zeros((0,), dtype=np.float64))

    normalized_strategy = (strategy or "").strip().lower()
    if normalized_strategy == "max":
        return cast(Array, similarity.max(axis=1))
    if normalized_strategy == "mean":
        return cast(Array, similarity.mean(axis=1))
    raise ValueError("similarity_aggregation must be 'max' or 'mean'.")


def _determine_centroid_count(
    *,
    liked_count: int,
    min_samples_per_centroid: int,
    dynamic_centroids: bool,
    centroid_scaling_factor: float,
) -> int:
    if liked_count <= 0:
        raise ValueError("liked_count must be positive.")

    if liked_count < max(1, min_samples_per_centroid):
        return 1

    if dynamic_centroids:
        dynamic = max(1, math.floor(liked_count * centroid_scaling_factor))
        return max(1, min(dynamic, liked_count))

    return max(1, min(liked_count // max(1, min_samples_per_centroid), liked_count))


def _run_kmeans(
    data: Array,
    *,
    n_clusters: int,
    random_state: int | None,
) -> Array:
    if data.shape[0] < n_clusters:
        raise ValueError(
            f"Cannot run KMeans with n_clusters={n_clusters} on {data.shape[0]} samples."
        )
    if n_clusters == 1:
        return cast(Array, data.mean(axis=0, keepdims=True))

    kmeans = KMeans(
        n_clusters=n_clusters,
        n_init="auto",
        random_state=random_state,
    )
    kmeans.fit(data)
    return cast(Array, kmeans.cluster_centers_)


def _format_result_row(row: dict[str, Any]) -> dict[str, Any]:
    playing_time_raw = row.get("playing_time_minutes")
    playing_time: int | None
    if playing_time_raw is None:
        playing_time = None
    else:
        try:
            playing_time_value = float(playing_time_raw)
            playing_time = None if math.isnan(playing_time_value) else int(playing_time_value)
        except (TypeError, ValueError):
            playing_time = None

    min_players = row.get("min_players")
    max_players = row.get("max_players")
    avg_rating = row.get("avg_rating")

    def _safe_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
            return None if math.isnan(number) else number
        except (TypeError, ValueError):
            return None

    return {
        "name": row.get("name"),
        "score": float(row.get("score", 0.0)),
        "avg_rating": _safe_float(avg_rating) or 0.0,
        "playing_time": playing_time,
        "min_players": _safe_int(min_players),
        "max_players": _safe_int(max_players),
    }
