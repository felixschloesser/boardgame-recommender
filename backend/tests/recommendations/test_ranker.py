from __future__ import annotations

import numpy as np
import pytest
from boardgames_api.domain.recommendations.reccomender import (
    AggregationStrategy,
    EmbeddingSimilarityRecommender,
    RecommendationUnavailableError,
    _build_preference_vectors,
    _run_kmeans,
)
from boardgames_api.domain.recommendations.reccomender import (
    np as rec_np,
)
from boardgames_api.infrastructure.embeddings import Embeddings


def _store(bgg_ids, vectors, names=None) -> Embeddings:
    norms = np.linalg.norm(vectors, axis=1)
    return Embeddings(
        run_identifier="test",
        bgg_ids=np.array(bgg_ids),
        vectors=np.array(vectors, dtype=float),
        norms=norms,
        names=names or {},
    )


def test_embedding_ranker_ranks_and_excludes_liked():
    store = _store(
        bgg_ids=[1, 2, 3],
        vectors=[
            [1.0, 0.0],  # liked
            [0.9, 0.1],  # very similar to liked
            [0.0, 1.0],  # orthogonal
        ],
    )
    # Patch loader to return our store
    recommender = EmbeddingSimilarityRecommender(aggregation=AggregationStrategy.MAX)
    # Patch loader to return our store
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.reccomender.load_embedding", lambda: store
    )

    ranked = recommender.recommend(liked_games=[1], num_results=2)
    ids = [c.bgg_id for c in ranked]
    assert 1 not in ids  # liked game excluded
    assert ids[0] == 2  # most similar first
    assert len(ranked) == 2


def test_embedding_ranker_keeps_scores_aligned_with_candidates(monkeypatch):
    """
    Regression: ensure scores stay aligned with candidate ids after removing liked items.
    Previously the score array included liked rows while candidate ids did not, which could
    assign the liked item's top score to the wrong id.
    """
    # liked id=1 is orthogonal to id=2 but similar to id=3
    store = _store(
        bgg_ids=[1, 2, 3],
        vectors=[
            [0.0, 1.0],  # liked
            [1.0, 0.0],  # should be low score
            [0.1, 0.9],  # should be highest score
        ],
    )
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.reccomender.load_embedding", lambda: store
    )
    recommender = EmbeddingSimilarityRecommender(aggregation=AggregationStrategy.MAX)

    ranked = recommender.recommend(liked_games=[1], num_results=2)
    ids = [c.bgg_id for c in ranked]
    assert ids == [3, 2]  # id 3 is closest to the liked vector


def test_embedding_ranker_raises_when_embedding_missing(monkeypatch):
    def _raise():
        raise RecommendationUnavailableError("Embedding data unavailable.")

    monkeypatch.setattr("boardgames_api.domain.recommendations.reccomender.load_embedding", _raise)
    ranker = EmbeddingSimilarityRecommender()
    with pytest.raises(Exception):
        ranker.recommend(liked_games=[1], num_results=1)


def test_embedding_ranker_raises_when_no_liked_embeddings(monkeypatch):
    store = _store(
        bgg_ids=[2],
        vectors=[[0.0, 1.0]],
    )
    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.reccomender.load_embedding", lambda: store
    )
    ranker = EmbeddingSimilarityRecommender()
    with pytest.raises(Exception):
        ranker.recommend(liked_games=[99], num_results=1)


def test_build_preference_vectors_caps_safe_centroids(monkeypatch):
    liked_matrix = np.eye(5)

    captured = {}

    def _spy_run_kmeans(data, n_clusters, random_state):
        captured["n_clusters"] = n_clusters
        return rec_np.ones((n_clusters, data.shape[1]))

    monkeypatch.setattr(
        "boardgames_api.domain.recommendations.reccomender._run_kmeans", _spy_run_kmeans
    )

    _build_preference_vectors(
        liked_matrix,
        min_samples_per_centroid=1,
        dynamic_centroids=True,
        centroid_scaling_factor=0.6,  # yields centroid_count=3, safe cap to liked_count//2=2
        random_state=123,
    )

    assert captured["n_clusters"] == 2  # max(1, min(3, max(1, 5//2)))


def test_run_kmeans_is_deterministic_with_seed():
    data = np.array(
        [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.0, 1.0],
            [0.1, 0.9],
        ]
    )
    centers_a = _run_kmeans(data, n_clusters=2, random_state=42)
    centers_b = _run_kmeans(data, n_clusters=2, random_state=42)
    np.testing.assert_allclose(centers_a, centers_b)


def test_build_preference_vectors_uses_mean_when_single_cluster():
    liked_matrix = np.array([[1.0, 0.0], [1.0, 0.0]])
    prefs = _build_preference_vectors(
        liked_matrix,
        min_samples_per_centroid=10,  # force mean path
        dynamic_centroids=True,
        centroid_scaling_factor=0.1,
        random_state=None,
    )
    np.testing.assert_allclose(prefs, np.array([[1.0, 0.0]]))
