"""Model training pipeline."""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, cast

import joblib
import numpy as np
import polars as pl
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm.auto import tqdm

from boardgame_recommender.config import Config
from boardgame_recommender.pipelines.preprocessing import (
    normalized_numeric_columns,
)

logger = logging.getLogger(__name__)


@dataclass
class TrainingArtifacts:
    """Bundle describing a finished training run and its exported paths."""

    run_identifier: str
    run_directory: Path
    model_path: Path
    catalog_path: Path
    metadata_path: Path
    row_count: int
    feature_dimension: int
    evaluation: dict[str, dict[str, float]] | None = None


def _build_text_series(
    data_frame: pl.DataFrame, column_names: Iterable[str]
) -> list[str]:
    """Collapse multiple string columns into a normalized text blob per row."""

    if not column_names:
        return [""] * data_frame.height
    subset_frame = data_frame.select(
        [pl.col(column_name).fill_null("").cast(str) for column_name in column_names]
    )
    concatenated_frame = subset_frame.select(
        pl.concat_str(
            [pl.col(column) for column in subset_frame.columns], separator=" "
        )
        .str.replace(r"\s+", " ")
        .str.strip_chars()
        .alias("text_blob")
    )
    return concatenated_frame.to_series().to_list()


def _ensure_latest_symlink(run_directory: Path) -> None:
    """Point ``latest`` helper symlink at the most recent run directory."""

    latest_symlink_path = run_directory.parent / "latest"
    try:
        if latest_symlink_path.exists() or latest_symlink_path.is_symlink():
            if latest_symlink_path.is_dir() and not latest_symlink_path.is_symlink():
                for child in latest_symlink_path.iterdir():
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                latest_symlink_path.rmdir()
            else:
                latest_symlink_path.unlink()
        latest_symlink_path.symlink_to(run_directory, target_is_directory=True)
    except OSError:
        (run_directory.parent / "latest.txt").write_text(
            run_directory.name, encoding="utf-8"
        )


def _split_tags(tag_value: str | None) -> list[str]:
    """Return normalized tokens extracted from a comma-separated string."""

    if not tag_value:
        return []
    return [token.strip() for token in tag_value.split(",") if token.strip()]


def _build_similarity_groups(data_frame: pl.DataFrame) -> list[set[int]]:
    """Build adjacency lists of games sharing category/mechanic tags."""

    tag_groups: dict[str, set[int]] = defaultdict(set)
    category_values = data_frame["categories"].fill_null("").to_list()
    mechanic_values = data_frame["mechanics"].fill_null("").to_list()

    for row_index, category_entry in enumerate(category_values):
        for token in _split_tags(category_entry):
            tag_groups[f"category::{token}"].add(row_index)
    for row_index, mechanic_entry in enumerate(mechanic_values):
        for token in _split_tags(mechanic_entry):
            tag_groups[f"mechanic::{token}"].add(row_index)

    positive_neighbor_sets: list[set[int]] = [set() for _ in range(data_frame.height)]
    for indices in tag_groups.values():
        if len(indices) < 2:
            continue
        for row_index in indices:
            positive_neighbor_sets[row_index].update(indices - {row_index})
    return positive_neighbor_sets


def _calculate_recall_at_top_k(
    embeddings: np.ndarray,
    positive_sets: list[set[int]],
    top_result_count: int = 10,
) -> dict[str, float] | None:
    """Compute recall@k style metrics using cosine similarity between vectors."""

    if embeddings.size == 0:
        return None

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = embeddings / norms

    hit_count = 0
    recall_total = 0.0
    query_count = 0

    for row_index, positive_neighbors in enumerate(positive_sets):
        if not positive_neighbors:
            continue
        similarity_scores = normalized @ normalized[row_index]
        similarity_scores[row_index] = -np.inf

        if similarity_scores.shape[0] <= top_result_count:
            top_indices = np.argsort(similarity_scores)[::-1]
        else:
            top_indices = np.argpartition(similarity_scores, -top_result_count)[
                -top_result_count:
            ]
            top_indices = top_indices[np.argsort(similarity_scores[top_indices])[::-1]]

        retrieved_indices = set(top_indices[:top_result_count])
        matching = retrieved_indices.intersection(positive_neighbors)
        if matching:
            hit_count += 1
        denominator = min(len(positive_neighbors), top_result_count)
        if denominator > 0:
            recall_total += len(matching) / denominator
        query_count += 1

    if query_count == 0:
        return None

    return {
        "top_k": top_result_count,
        "hit_rate": hit_count / query_count,
        "mean_recall": recall_total / query_count,
        "num_queries": query_count,
    }


def train(
    processed_dataset_path: Path | None,
    configuration: Config,
    output_directory_override: Path | None = None,
    show_progress_bar: bool = False,
) -> TrainingArtifacts:
    """Build TF-IDF + SVD embeddings and persist embedding."""

    processed_path = Path(
        processed_dataset_path or configuration.paths.processed_features
    )
    output_directory = Path(
        output_directory_override or configuration.paths.models_directory
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    logger.info("Loading processed dataset from %s", processed_path)
    processed_frame = pl.read_parquet(processed_path)

    total_steps = 3
    progress_tracker = tqdm(
        total=total_steps,
        desc="Training pipeline (embedding)",
        disable=not show_progress_bar,
        unit="step",
    )

    logger.info(
        "Building text series from columns: %s",
        configuration.features.text_columns,
    )
    text_series = _build_text_series(
        processed_frame, configuration.features.text_columns
    )
    progress_tracker.update(1)

    svd_config = configuration.singular_value_decomposition
    logger.info(
        "Fitting TF-IDF (max_features=%s, min_df=%s) + numeric features + "
        "TruncatedSVD (n_components=%s)",
        svd_config.maximum_features,
        svd_config.minimum_document_frequency,
        svd_config.component_count,
    )
    text_vectorizer = TfidfVectorizer(
        max_features=svd_config.maximum_features,
        min_df=svd_config.minimum_document_frequency,
    )
    singular_value_decomposition_model = TruncatedSVD(
        n_components=svd_config.component_count, random_state=svd_config.random_state
    )

    text_matrix = text_vectorizer.fit_transform(text_series)
    numeric_feature_names = normalized_numeric_columns(
        configuration.features.numeric_columns
    )

    missing_numeric_columns = [
        column_name
        for column_name in numeric_feature_names
        if column_name not in processed_frame.columns
    ]
    if missing_numeric_columns:
        raise ValueError(
            "Processed dataset missing normalized numeric columns: "
            f"{', '.join(missing_numeric_columns)}"
        )

    combined_feature_matrix = text_matrix
    if numeric_feature_names:
        numeric_feature_array = (
            processed_frame.select(numeric_feature_names).to_numpy().astype(np.float64)
        )
        numeric_feature_array = np.nan_to_num(numeric_feature_array, nan=0.0)
        numeric_feature_matrix = sparse.csr_matrix(numeric_feature_array)
        combined_feature_matrix = sparse.hstack([text_matrix, numeric_feature_matrix])

    embedding_matrix = singular_value_decomposition_model.fit_transform(
        combined_feature_matrix
    )
    progress_tracker.update(1)

    feature_dimension = svd_config.component_count

    run_identifier = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_directory = output_directory / run_identifier
    run_directory.mkdir(parents=True, exist_ok=True)

    model_path = run_directory / "model.pkl"
    catalog_path = run_directory / "embeddings.parquet"
    metadata_path = run_directory / "metadata.json"

    model_components = {
        "vectorizer": text_vectorizer,
        "svd": singular_value_decomposition_model,
    }
    joblib.dump(model_components, model_path)

    embedding_columns = [f"svd_{i}" for i in range(svd_config.component_count)]
    embedding_frame = pl.DataFrame(embedding_matrix, schema=embedding_columns)

    catalog_base_columns = [
        "bgg_id",
        "name",
        "avg_rating",
        "min_players",
        "max_players",
        "playing_time_minutes",
        "mechanics",
        "categories",
    ]
    catalog_components: list[pl.DataFrame] = [
        processed_frame.select(catalog_base_columns),
        embedding_frame,
    ]
    catalog_with_embeddings = pl.concat(catalog_components, how="horizontal")

    positive_neighbor_sets = _build_similarity_groups(processed_frame)
    recall_metrics = _calculate_recall_at_top_k(
        embedding_matrix, positive_neighbor_sets, top_result_count=10
    )

    catalog_with_embeddings.write_parquet(catalog_path)

    metadata_payload: dict[str, Any] = {
        "run_identifier": run_identifier,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "row_count": processed_frame.height,
        "feature_dimension": feature_dimension,
        "feature_columns": {
            "text": configuration.features.text_columns,
            "numeric": configuration.features.numeric_columns,
        },
        "model": {
            "type": "embedding",
            "embedding_dimension": svd_config.component_count,
            "vectorizer": {
                "maximum_features": svd_config.maximum_features,
                "minimum_document_frequency": svd_config.minimum_document_frequency,
            },
        },
    }
    if recall_metrics is not None:
        metadata_payload["evaluation"] = {"recall_at_10": recall_metrics}

    _ensure_latest_symlink(run_directory)
    progress_tracker.update(1)
    progress_tracker.close()

    evaluation_data = cast(
        dict[str, dict[str, float]] | None, metadata_payload.get("evaluation")
    )

    return TrainingArtifacts(
        run_identifier=run_identifier,
        run_directory=run_directory,
        model_path=model_path,
        catalog_path=catalog_path,
        metadata_path=metadata_path,
        row_count=processed_frame.height,
        feature_dimension=feature_dimension,
        evaluation=evaluation_data,
    )
