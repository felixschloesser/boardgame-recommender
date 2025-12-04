from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np
import polars as pl
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm.auto import tqdm

from boardgames_cli.config import (
    Config,
    FeatureWeightsConfig,
    TextVectorizationConfig,
)
from boardgames_cli.utils.transforms import normalize_rows

logger = logging.getLogger(__name__)


@dataclass
class Embedding:
    """
    Learned embedding for all games in the catalog.

    - `vectors` holds one row per game including:
        * base metadata columns (bgg_id, name, ratings, players, time)
        * embedding_dimension_* columns representing the low-dimensional embedding.
    - `metadata` contains training configuration and schema details.
    """

    run_identifier: str
    vectors: pl.DataFrame
    metadata: dict[str, Any]

    def __str__(self) -> str:  # pragma: no cover - human-readable debug repr
        return (
            f"Embedding(run_id={self.run_identifier}, rows={self.vectors.height}, "
            f"dimensions={len(self.metadata.get('embedding_columns', []))})"
        )

    @staticmethod
    def train(
        features: pl.DataFrame,
        config: Config,
        show_progress: bool = False,
    ) -> Embedding:
        """
        Train a low-dimensional similarity embedding from preprocessed features.

        Expected input schema (configurable upstream):
        - text_* columns: free text facets (description, mechanics, categories, themes, ...)
        - cat_* columns: categorical / token-like text features
        - num_* columns: numeric features (weights, normalized counts, etc.)

        The pipeline:
            1. Per-column TF-IDF for text/categorical features with configurable weights.
            2. Numeric features as a dense block with its own weight.
            3. Feature matrix concatenation (scipy.sparse.hstack).
            4. TruncatedSVD for dimensionality reduction.
            5. Optional L2 row-normalization of the resulting embedding vectors.
            6. Construction of a Polars DataFrame with base metadata +
               embedding_dimension_* columns.
        """
        if features.is_empty():
            raise ValueError("Cannot train on an empty feature table.")

        schema = _infer_feature_schema(features)
        if not schema.has_any_features:
            raise ValueError(
                "No training features detected; expected text_*, cat_* or num_* columns. "
                "Run preprocessing first."
            )

        progress = tqdm(
            total=3,
            desc="Training embedding",
            unit="stage",
            disable=not show_progress,
        )

        if show_progress:
            logger.info(
                "Building sparse feature matrix from text and categorical signals ..."
            )
        text_blocks = _build_text_blocks(
            frame=features,
            columns=[*schema.text_columns, *schema.categorical_columns],
            weights=config.preprocessing.features.weights,
            text_config=config.training.text_vectorization,
        )
        progress.update(1)

        if show_progress:
            logger.info("Appending numeric structure to feature matrix ...")
        numeric_block = _build_numeric_block(
            frame=features,
            columns=schema.numeric_columns,
            weight=config.preprocessing.features.weights.numeric,
        )

        blocks = [block for block in (*text_blocks, numeric_block) if block is not None]
        if not blocks:
            raise ValueError("Failed to build any feature matrices for training.")

        feature_matrix = sparse.hstack(blocks, format="csr")
        progress.update(1)

        embedding_config = config.training.embedding_model
        if embedding_config.embedding_dimensions <= 0:
            raise ValueError("embedding_dimensions must be greater than zero.")

        if show_progress:
            logger.info(
                "Computing low-dimensional similarity embedding via TruncatedSVD "
                "(%d dimensions) ...",
                embedding_config.embedding_dimensions,
            )
        svd = TruncatedSVD(
            n_components=embedding_config.embedding_dimensions,
            random_state=config.random_seed,
        )
        embedding_matrix = svd.fit_transform(feature_matrix).astype(
            np.float64, copy=False
        )

        if embedding_config.normalize_embedding_vectors:
            embedding_matrix = normalize_rows(embedding_matrix)

        progress.update(1)
        progress.close()

        embedding_columns = [
            f"embedding_dimension_{index}"
            for index in range(embedding_config.embedding_dimensions)
        ]
        base_columns = _base_columns(features)

        vectors = pl.concat(
            [
                features.select(base_columns),
                pl.DataFrame(embedding_matrix, schema=embedding_columns),
            ],
            how="horizontal",
        )

        run_identifier = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        created_at = datetime.now(timezone.utc).isoformat()

        metadata: dict[str, Any] = {
            "run_identifier": run_identifier,
            "created_at": created_at,
            "row_count": features.height,
            "embedding_columns": embedding_columns,
            "embedding_dimensions": embedding_config.embedding_dimensions,
            "training_config": config.training.model_dump(mode="json"),
            "feature_schema": {
                "text": schema.text_columns,
                "categorical": schema.categorical_columns,
                "numeric": schema.numeric_columns,
            },
            "config": config.model_dump(mode="json"),
        }

        return Embedding(
            run_identifier=run_identifier, vectors=vectors, metadata=metadata
        )


def train(
    *,
    features: pl.DataFrame,
    config: Config,
    show_progress: bool = False,
) -> Embedding:
    """
    Convenience wrapper around Embedding.train retained for backward compatibility.
    """
    return Embedding.train(
        features=features, config=config, show_progress=show_progress
    )


@dataclass
class _FeatureSchema:
    text_columns: list[str]
    categorical_columns: list[str]
    numeric_columns: list[str]

    @property
    def has_any_features(self) -> bool:
        return bool(
            self.text_columns or self.categorical_columns or self.numeric_columns
        )


def _infer_feature_schema(frame: pl.DataFrame) -> _FeatureSchema:
    """
    Identify which columns participate in training based on naming convention.
    """
    text_columns = _prefixed_columns(frame, "text_")
    categorical_columns = _prefixed_columns(frame, "cat_")
    numeric_columns = _prefixed_columns(frame, "num_")

    return _FeatureSchema(
        text_columns=text_columns,
        categorical_columns=categorical_columns,
        numeric_columns=numeric_columns,
    )


def _prefixed_columns(frame: pl.DataFrame, prefix: str) -> list[str]:
    return [column for column in frame.columns if column.startswith(prefix)]


def _build_text_blocks(
    *,
    frame: pl.DataFrame,
    columns: Sequence[str],
    weights: FeatureWeightsConfig,
    text_config: TextVectorizationConfig,
) -> list[sparse.csr_matrix]:
    """
    Build one TF-IDF block per text/categorical column.

    Rationale:
    - Separate vectorizers per facet allows domain experts to adjust weights independently.
    - We apply scalar weights *before* SVD so that embedding dimensions remain interpretable.
    """
    blocks: list[sparse.csr_matrix] = []

    for column in columns:
        if column not in frame.columns:
            logger.warning("Feature column '%s' missing; skipping.", column)
            continue

        values = [
            value if isinstance(value, str) else ("" if value is None else str(value))
            for value in frame[column].to_list()
        ]
        has_content = any(value.strip() for value in values if isinstance(value, str))
        if not has_content:
            logger.info(
                "Feature column '%s' empty after preprocessing; skipping.", column
            )
            continue

        vectorizer = TfidfVectorizer(
            min_df=text_config.min_document_occurrences,
            max_df=text_config.max_document_frequency,
            norm="l2" if text_config.equalize_description_length else None,
            sublinear_tf=text_config.downweight_repeated_terms,
        )

        try:
            matrix = vectorizer.fit_transform(values)
        except ValueError:
            logger.info(
                "TfidfVectorizer for column '%s' produced no features; skipping.",
                column,
            )
            continue

        matrix = sparse.csr_matrix(matrix, copy=False)
        weight = _column_weight(column, weights)

        if weight != 1.0:
            matrix = matrix.multiply(weight)

        blocks.append(matrix)

    return blocks


def _column_weight(column: str, weights: FeatureWeightsConfig) -> float:
    """
    Map a feature column suffix to its configured weight.

    We assume feature naming like:
        text_description_tokens, text_mechanics, text_categories, text_themes, ...

    Fallback to 1.0 for unknown suffixes so adding new columns is safe by default.
    """
    suffix = column
    if suffix.startswith("text_"):
        suffix = suffix[len("text_") :]
    if suffix.endswith("_tokens"):
        suffix = suffix[: -len("_tokens")]
    elif "_" in suffix:
        suffix = suffix.split("_", 1)[1]
    weights_map: dict[str, float] = {
        "description": weights.description,
        "mechanics": weights.mechanics,
        "categories": weights.categories,
        "themes": weights.themes,
    }
    return weights_map.get(suffix, 1.0)


def _build_numeric_block(
    *,
    frame: pl.DataFrame,
    columns: Sequence[str],
    weight: float,
) -> sparse.csr_matrix | None:
    """
    Build a dense numeric feature block.

    We assume upstream preprocessing already handled scaling/normalization if desired.
    """
    if not columns:
        return None

    matrix = frame.select(columns).to_numpy().astype("float64", copy=False)

    if not np.isfinite(matrix).all():
        raise ValueError(
            "Numeric features contain invalid values; check preprocessing."
        )

    if weight != 1.0:
        matrix = matrix * float(weight)

    return sparse.csr_matrix(matrix)


def _base_columns(frame: pl.DataFrame) -> list[str]:
    """
    Base metadata columns that are carried over into the embedding DataFrame.
    """
    candidates = (
        "bgg_id",
        "name",
        "description",
        "avg_rating",
        "min_players",
        "max_players",
        "playing_time_minutes",
    )
    return [column for column in candidates if column in frame.columns]
