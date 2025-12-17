from __future__ import annotations

import math
import os
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import KMeans

from boardgames_api.domain.recommendations.exceptions import RecommendationUnavailableError
from boardgames_api.infrastructure.embeddings import Embeddings, load_embedding

Array = NDArray[np.float64]


class AggregationStrategy(Enum):
    MEAN = "mean"
    MAX = "max"


@dataclass
class ScoredGameId:
    score: float
    bgg_id: int


@dataclass
class PreferenceClusterConfig:
    min_samples_per_centroid: int = 2
    dynamic_centroids: bool = True
    centroid_scaling_factor: float = 0.5


class Recommender(Protocol):
    def recommend(
        self,
        liked_games: Iterable[int],
        num_results: int,
    ) -> list[ScoredGameId]: ...


class EmbeddingSimilarityRecommender:
    """
    Suggest similar games by ranking embedded games against preference centroids.
    """

    def __init__(
        self,
        aggregation: AggregationStrategy = AggregationStrategy.MEAN,
        preference_cluster: PreferenceClusterConfig | None = None,
        random_state: int | None = None,
    ) -> None:
        self.aggregation = aggregation
        self.preference_cluster = preference_cluster or PreferenceClusterConfig()
        env_seed = os.getenv("BOARDGAMES_RECOMMENDER_RANDOM_SEED")
        self.random_state = int(env_seed) if env_seed is not None else random_state

    def recommend(
        self,
        liked_games: Iterable[int],
        num_results: int,
    ) -> list[ScoredGameId]:
        if num_results <= 0:
            raise RecommendationUnavailableError("num_results must be positive.")

        embedding = load_embedding()

        liked_ids = [int(liked) for liked in liked_games if embedding.has_id(int(liked))]
        missing = [int(liked) for liked in liked_games if not embedding.has_id(int(liked))]
        if missing and liked_ids:
            # Proceed with available liked ids but surface what is missing.
            # Upstream can decide whether to expose this detail.
            pass
        if not liked_ids:
            raise RecommendationUnavailableError(
                "No embeddings available for the liked games; choose games that exist "
                "in the dataset."
            )

        id_index = {int(bgg_id): idx for idx, bgg_id in enumerate(embedding.bgg_ids)}
        liked_indices: list[int] = [id_index[gid] for gid in liked_ids if gid in id_index]
        liked_matrix = embedding.vectors[liked_indices]
        preference_vectors = _build_preference_vectors(
            liked_matrix,
            dynamic_centroids=self.preference_cluster.dynamic_centroids,
            min_samples_per_centroid=self.preference_cluster.min_samples_per_centroid,
            centroid_scaling_factor=self.preference_cluster.centroid_scaling_factor,
            random_state=self.random_state,
        )

        filtered_candidate_ids, cand_matrix, cand_norms = _filter_candidates(embedding, liked_ids)

        # Score all candidates by cosine similarity to preference centroids, then sort.
        scores = _score_candidates(
            cand_matrix,
            preference_vectors,
            strategy=self.aggregation,
            candidate_norms=cand_norms,
        )

        ranked: list[ScoredGameId] = []
        for cid, score in zip(filtered_candidate_ids, scores):
            ranked.append(ScoredGameId(bgg_id=int(cid), score=float(score)))

        ranked = sorted(ranked, key=lambda item: item.score, reverse=True)
        return ranked[:num_results]


def _build_preference_vectors(
    liked_matrix: Array,
    min_samples_per_centroid: int,
    dynamic_centroids: bool,
    centroid_scaling_factor: float,
    random_state: int | None,
) -> Array:
    if liked_matrix.size == 0:
        raise RecommendationUnavailableError(
            "Liked games could not be mapped to the embedding space."
        )

    liked_count = liked_matrix.shape[0]
    centroid_count = _determine_centroid_count(
        liked_count=liked_count,
        min_samples_per_centroid=min_samples_per_centroid,
        dynamic_centroids=dynamic_centroids,
        centroid_scaling_factor=centroid_scaling_factor,
    )

    if centroid_count == 1 or liked_count <= centroid_count:
        preference_vectors = liked_matrix.mean(axis=0, keepdims=True)
    else:
        safe_centroids = max(1, min(centroid_count, max(1, liked_count // 2)))
        preference_vectors = _run_kmeans(
            liked_matrix,
            n_clusters=safe_centroids,
            random_state=random_state,
        )

    return _normalize_rows(preference_vectors)


def _determine_centroid_count(
    liked_count: int,
    min_samples_per_centroid: int,
    dynamic_centroids: bool,
    centroid_scaling_factor: float,
) -> int:
    if liked_count <= 0:
        raise RecommendationUnavailableError("liked_count must be positive.")

    if liked_count < max(1, min_samples_per_centroid):
        return 1

    if dynamic_centroids:
        dynamic = max(1, math.floor(liked_count * centroid_scaling_factor))
        return max(1, min(dynamic, liked_count))

    return max(1, min(liked_count // max(1, min_samples_per_centroid), liked_count))


def _run_kmeans(
    data: Array,
    n_clusters: int,
    random_state: int | None,
) -> Array:
    if data.shape[0] < n_clusters:
        raise RecommendationUnavailableError(
            f"Cannot run k-means with n_clusters={n_clusters} on {data.shape[0]} samples."
        )
    if n_clusters == 1:
        return data.mean(axis=0, keepdims=True)

    kmeans = KMeans(
        n_clusters=n_clusters,
        n_init="auto",
        random_state=random_state,
    )
    kmeans.fit(data)
    return kmeans.cluster_centers_


def _filter_candidates(
    embedding: Embeddings, liked_ids: list[int]
) -> tuple[list[int], Array, Array]:
    """
    Remove liked ids and return (candidate_ids, candidate_vectors, candidate_norms)
    with aligned ordering.
    """
    bgg_ids = np.asarray(embedding.bgg_ids, dtype=int)
    mask = ~np.isin(bgg_ids, liked_ids)
    candidate_ids = bgg_ids[mask].tolist()
    return candidate_ids, embedding.vectors[mask], embedding.norms[mask]


def _cosine_similarity(candidates: Array, targets: Array) -> Array:
    if candidates.size == 0 or targets.size == 0:
        empty = np.zeros((candidates.shape[0], targets.shape[0]), dtype=np.float64)
        return empty
    # Normalize rows
    candidates_norm = _normalize_rows(candidates)
    targets_norm = _normalize_rows(targets)
    return candidates_norm @ targets_norm.T


def _normalize_rows(matrix: Array, norms: Array | None = None) -> Array:
    if norms is None:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    else:
        norms = norms.reshape(-1, 1)
    norms = norms.astype(np.float64, copy=True)
    norms[norms == 0.0] = 1e-12
    return matrix / norms


def _score_candidates(
    candidates: Array,
    preferences: Array,
    strategy: AggregationStrategy,
    candidate_norms: Array | None = None,
) -> Array:
    if candidate_norms is None:
        similarity = _cosine_similarity(candidates, preferences)
    else:
        similarity = _cosine_similarity(
            _normalize_rows(candidates, norms=candidate_norms), preferences
        )
    if similarity.size == 0:
        return np.zeros((0,), dtype=np.float64)

    if strategy == AggregationStrategy.MAX:
        return similarity.max(axis=1)
    if strategy == AggregationStrategy.MEAN:
        return similarity.mean(axis=1)
    raise RecommendationUnavailableError(
        "aggregation must be AggregationStrategy.MAX or AggregationStrategy.MEAN."
    )
