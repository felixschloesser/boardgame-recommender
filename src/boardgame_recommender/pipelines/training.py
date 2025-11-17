from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np
import polars as pl
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm.auto import tqdm

from boardgame_recommender.config import Config
from boardgame_recommender.pipelines.preprocessing import normalized_numeric_columns

logger = logging.getLogger(__name__)


@dataclass
class Embedding:
    run_identifier: str
    vectors: pl.DataFrame
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return (
            f"Embedding(run_id={self.run_identifier}, "
            f"rows={self.vectors.height}, "
            f"dimensions={self.metadata.get('feature_dimension')})"
        )


def _non_empty_strings(values: Iterable[str | None]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        cleaned.append(value.strip() if isinstance(value, str) else "")
    return cleaned


def _vectorize_column(
    series: pl.Series,
    tfidf_config,
    ngram_range: tuple[int, int],
) -> sparse.csr_matrix | None:
    values = _non_empty_strings(series.to_list())
    if not any(value for value in values):
        return None
    vectorizer = TfidfVectorizer(
        min_df=tfidf_config.min_document_occurences,
        max_df=tfidf_config.max_document_frequency,
        max_features=tfidf_config.max_features,
        norm=tfidf_config.normalization_strategy,
        sublinear_tf=tfidf_config.sublinear,
        ngram_range=ngram_range,
    )
    try:
        matrix = vectorizer.fit_transform(values)
    except ValueError:
        return None
    return sparse.csr_matrix(matrix)


def _build_text_matrix(
    features: pl.DataFrame,
    column_names: list[str],
    tfidf_config,
    token_config,
    weights_lookup: dict[str, float],
) -> sparse.csr_matrix | None:
    blocks: list[sparse.csr_matrix] = []
    for column in column_names:
        if column not in features.columns:
            logger.warning("Text column '%s' missing; skipping", column)
            continue
        block = _vectorize_column(features[column], tfidf_config, token_config.ngram_range)
        if block is None:
            continue
        weight = weights_lookup.get(column, 1.0)
        if weight != 1.0:
            block = block.multiply(weight)
        blocks.append(block)
    if not blocks:
        return None
    return sparse.hstack(blocks).tocsr()


def _build_numeric_matrix(
    features: pl.DataFrame,
    numeric_columns: list[str],
    weight: float,
) -> sparse.csr_matrix | None:
    if not numeric_columns:
        return None
    missing = [column for column in numeric_columns if column not in features.columns]
    if missing:
        raise ValueError(
            "Preprocessed dataset is missing normalized numeric columns: "
            f"{', '.join(missing)}"
        )
    numeric_array = features.select(numeric_columns).to_numpy().astype(float)
    if np.isnan(numeric_array).any():
        raise ValueError(
            "Numeric feature matrix contains NaN values after preprocessing; check null handling."
        )
    if weight != 1.0:
        numeric_array *= weight
    return sparse.csr_matrix(numeric_array)


def _base_vectors(features: pl.DataFrame) -> pl.DataFrame:
    base_columns = [
        column
        for column in (
            "bgg_id",
            "name",
            "avg_rating",
            "min_players",
            "max_players",
            "playing_time_minutes",
        )
        if column in features.columns
    ]
    return features.select(base_columns)


def train(
    features: pl.DataFrame,
    config: Config,
    show_progress: bool = False,
) -> Embedding:
    """
    Train a TF-IDF + TruncatedSVD embedding over the curated feature table.
    """

    if features.is_empty():
        raise ValueError("Cannot train on an empty dataset; run preprocessing first.")

    progress = tqdm(
        total=3,
        desc="Training embedding",
        disable=not show_progress,
        unit="stage",
    )

    preprocessing_config = config.preprocessing
    training_config = config.training
    tfidf_config = training_config.tfidf
    svd_config = training_config.svd

    weights = preprocessing_config.features.weights
    weights_lookup = {
        "description": weights.description,
        "mechanics": weights.mechanics,
        "categories": weights.categories,
        "themes": weights.themes,
    }

    text_columns = list(preprocessing_config.features.text.columns)
    categorical_columns = list(preprocessing_config.features.categorical.columns)
    text_matrix = _build_text_matrix(
        features,
        [*text_columns, *categorical_columns],
        tfidf_config,
        preprocessing_config.tokenization,
        weights_lookup,
    )
    progress.update(1)

    numeric_sources: list[str] = []
    numeric_config = preprocessing_config.features.numeric
    numeric_sources.extend(numeric_config.normal.columns)
    numeric_sources.extend(numeric_config.heavy_tail.columns)
    numeric_columns = normalized_numeric_columns(numeric_sources)
    numeric_matrix = _build_numeric_matrix(features, numeric_columns, weight=weights.numeric)

    blocks = [block for block in (text_matrix, numeric_matrix) if block is not None]
    if not blocks:
        raise ValueError("No usable features were produced for training.")
    feature_matrix = sparse.hstack(blocks).tocsr()
    progress.update(1)

    svd = TruncatedSVD(
        n_components=svd_config.latent_dimensions,
        n_iter=svd_config.iterations,
        random_state=config.random.seed,
    )
    embedding_matrix = svd.fit_transform(feature_matrix)
    progress.update(1)
    progress.close()

    embedding_columns = [
        f"svd_{index}" for index in range(svd_config.latent_dimensions)
    ]
    vectors = pl.concat(
        [
            _base_vectors(features),
            pl.DataFrame(embedding_matrix, schema=embedding_columns),
        ],
        how="horizontal",
    )

    run_identifier = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    metadata: dict[str, Any] = {
        "run_identifier": run_identifier,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "row_count": features.height,
        "feature_dimension": len(embedding_columns),
        "feature_columns": {
            "text": text_columns,
            "categorical": categorical_columns,
            "numeric": numeric_columns,
        },
        "cutoff": {
            "metric": preprocessing_config.cutoff_metric,
            "quantile": preprocessing_config.cutoff_quantile,
        },
        "model": {
            "tfidf": {
                "min_document_occurrences": tfidf_config.min_document_occurences,
                "max_document_frequency": tfidf_config.max_document_frequency,
                "max_features": tfidf_config.max_features,
                "normalization": tfidf_config.normalization_strategy,
                "sublinear_tf": tfidf_config.sublinear,
            },
            "svd": {
                "latent_dimensions": svd_config.latent_dimensions,
                "iterations": svd_config.iterations,
            },
        },
    }

    return Embedding(run_identifier=run_identifier, vectors=vectors, metadata=metadata)
