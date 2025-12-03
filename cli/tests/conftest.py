from __future__ import annotations

import os
import sys
from pathlib import Path

import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Stabilize joblib CPU detection warning in tests.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")

from boardgames_cli.config import (  # noqa: E402
    Config,
    EmbeddingModelConfig,
    FeaturesConfig,
    FeatureWeightsConfig,
    PathsConfig,
    PreferenceClusterConfig,
    PreprocessingConfig,
    PreprocessingFilters,
    RecommendationConfig,
    TextVectorizationConfig,
    TokenizationConfig,
    TrainingConfig,
)
from boardgames_cli.pipelines.training import Embedding  # noqa: E402
from boardgames_cli.recommend import RecommendationContext  # noqa: E402


@pytest.fixture
def config() -> Config:
    paths = PathsConfig(
        stopwords_file=Path("/tmp/stopwords.txt"),
        synonyms_file=Path("/tmp/synonyms.toml"),
        raw_data_directory=Path("/tmp/raw"),
        processed_features_directory=Path("/tmp/processed"),
        embeddings_directory=Path("/tmp/embeddings"),
    )

    filters = PreprocessingFilters(
        max_year=2025,
        min_popularity_quantile=0.2,
        min_avg_rating=5.0,
        max_required_players=8,
        max_playing_time_minutes=240,
    )

    feature_weights = FeatureWeightsConfig(
        description=1.0,
        mechanics=0.8,
        categories=0.9,
        themes=0.7,
        numeric=0.5,
    )

    features = FeaturesConfig(
        text=["description"],
        categorical=["mechanics"],
        numeric=["avg_rating", "min_players", "max_players"],
        weights=feature_weights,
    )

    tokenization = TokenizationConfig(
        unify_synonyms=True,
        remove_common_domain_words=True,
        ngram_range=(1, 2),
    )

    preprocessing = PreprocessingConfig(
        filters=filters,
        features=features,
        tokenization=tokenization,
    )

    training = TrainingConfig(
        text_vectorization=TextVectorizationConfig(
            min_document_occurrences=1,
            max_document_frequency=1.0,
            equalize_description_length=True,
            downweight_repeated_terms=False,
        ),
        embedding_model=EmbeddingModelConfig(
            normalize_embedding_vectors=False,
            embedding_dimensions=2,
        ),
    )

    recommendation = RecommendationConfig(
        similarity_aggregation="max",
        preference_cluster=PreferenceClusterConfig(
            min_samples_per_centroid=2,
            dynamic_centroids=False,
            centroid_scaling_factor=0.5,
        ),
        random_seed=7,
    )

    return Config(
        random_seed=7,
        logging_level="INFO",
        paths=paths,
        preprocessing=preprocessing,
        training=training,
        recommendation=recommendation,
    )


@pytest.fixture
def recommendation_config(config: Config) -> RecommendationConfig:
    return config.recommendation.model_copy(deep=True)


@pytest.fixture
def sample_features() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "bgg_id": [1, 2, 3, 4],
            "name": ["Alpha", "Beta", "Gamma", "Delta"],
            "description": [
                "Cooperative adventure game with dice rolling",
                "Economic engine builder with worker placement",
                "Light party card game focused on bluffing",
                "Area control battle with asymmetric factions",
            ],
            "text_description_tokens": [
                "Cooperative adventure game with dice rolling",
                "Economic engine builder with worker placement",
                "Light party card game focused on bluffing",
                "Area control battle with asymmetric factions",
            ],
            "cat_mechanics": [
                "dice rolling,cooperative",
                "worker placement,engine building",
                "party,bluffing",
                "area control,combat",
            ],
            "num_avg_rating": [7.8, 7.1, 6.5, 8.2],
            "num_min_players": [1, 2, 2, 3],
            "num_max_players": [4, 4, 6, 5],
            "num_complexity": [2.1, 3.4, 1.2, 3.8],
            "min_players": [1, 2, 2, 3],
            "max_players": [4, 4, 6, 5],
            "playing_time_minutes": [60, 90, 30, 120],
        }
    )


@pytest.fixture
def sample_embedding() -> Embedding:
    vectors = pl.DataFrame(
        {
            "bgg_id": [1, 2, 3, 4, 5],
            "name": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
            "avg_rating": [7.5, 7.0, None, 8.2, 6.1],
            "min_players": [1, 2, 2, 3, 1],
            "max_players": [4, 4, 5, 5, 3],
            "playing_time_minutes": [60, 45, 30, 120, 20],
            "embedding_dimension_0": [1.0, 1.0, 0.5, 0.0, 0.2],
            "embedding_dimension_1": [0.0, 0.0, 0.5, 1.0, 0.8],
        }
    )
    metadata = {
        "embedding_columns": ["embedding_dimension_0", "embedding_dimension_1"],
    }
    return Embedding(run_identifier="test", vectors=vectors, metadata=metadata)


@pytest.fixture
def recommendation_context(
    sample_embedding, recommendation_config
) -> RecommendationContext:
    return RecommendationContext.from_embedding(
        embedding=sample_embedding,
        config=recommendation_config,
    )

