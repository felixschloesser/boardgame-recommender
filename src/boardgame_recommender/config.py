from pathlib import Path
from typing import List, Optional, Tuple, Union

import tomllib
from pydantic import BaseModel, Field

PROCESSED_FEATURES_FILENAME = "boardgames.parquet"
DATA_QUALITY_REPORT_FILENAME = "data_quality.json"

# --------------------------------------
# PATH CONFIG
# --------------------------------------


class PathsConfig(BaseModel):
    stopwords_file: Path
    synonyms_file: Path
    raw_data_directory: Path
    processed_features_directory: Path
    embeddings_directory: Path

    @property
    def processed_features_file(self) -> Path:
        return self.processed_features_directory / PROCESSED_FEATURES_FILENAME

    @property
    def data_quality_report_file(self) -> Path:
        return self.processed_features_directory / DATA_QUALITY_REPORT_FILENAME


# --------------------------------------
# PREPROCESSING: FILTERS
# --------------------------------------


class PreprocessingFilters(BaseModel):
    max_year: Optional[int]
    min_popularity_quantile: float = Field(ge=0.0, le=1.0)
    min_avg_rating: float
    max_required_players: int
    max_playing_time_minutes: int


class FeatureWeightsConfig(BaseModel):
    description: float
    mechanics: float
    categories: float
    themes: float
    numeric: float


# --------------------------------------
# FEATURES
# --------------------------------------


class FeaturesConfig(BaseModel):
    text: List[str]
    categorical: List[str]
    numeric: List[str]
    weights: FeatureWeightsConfig


# --------------------------------------
# TOKENIZATION
# --------------------------------------


class TokenizationConfig(BaseModel):
    unify_synonyms: bool
    remove_common_domain_words: bool
    ngram_range: Tuple[int, int]


# --------------------------------------
# TEXT VECTORIZATION
# --------------------------------------


class TextVectorizationConfig(BaseModel):
    min_document_occurrences: int
    max_document_frequency: float
    equalize_description_length: bool
    downweight_repeated_terms: bool


# --------------------------------------
# TASTE MODEL
# --------------------------------------


class TasteModelConfig(BaseModel):
    normalize_taste_vectors: bool
    taste_dimensions: int


# --------------------------------------
# RECOMMENDATION
# --------------------------------------


class RecommendationTasteModelConfig(BaseModel):
    min_samples_per_centroid: int
    dynamic_centroids: bool
    centroid_scaling_factor: float


class RecommendationConfig(BaseModel):
    similarity_aggregation: str
    taste_model: RecommendationTasteModelConfig
    random_seed: Optional[int] = None


# --------------------------------------
# PREPROCESSING (TOP LEVEL)
# --------------------------------------


class PreprocessingConfig(BaseModel):
    filters: PreprocessingFilters
    features: FeaturesConfig
    tokenization: TokenizationConfig


# --------------------------------------
# TRAINING
# --------------------------------------


class TrainingConfig(BaseModel):
    text_vectorization: TextVectorizationConfig
    taste_model: TasteModelConfig


# --------------------------------------
# FULL CONFIG
# --------------------------------------


class Config(BaseModel):
    random_seed: int
    logging_level: str
    paths: PathsConfig
    preprocessing: PreprocessingConfig
    training: TrainingConfig
    recommendation: RecommendationConfig


# --------------------------------------
# LOAD FUNCTION
# --------------------------------------


def _resolve_path(base: Path, value: Path) -> Path:
    return value if value.is_absolute() else (base / value).resolve()


def load_config(path: Union[str, Path]) -> Config:
    path_obj = Path(path)
    data = tomllib.loads(path_obj.read_text("utf-8"))
    config = Config.model_validate(data)

    base = path_obj.parent.resolve()

    # correct property names to match TOML
    config.paths.stopwords_file = _resolve_path(base, config.paths.stopwords_file)
    config.paths.synonyms_file = _resolve_path(base, config.paths.synonyms_file)
    config.paths.raw_data_directory = _resolve_path(
        base, config.paths.raw_data_directory
    )
    config.paths.processed_features_directory = _resolve_path(
        base, config.paths.processed_features_directory
    )
    config.paths.embeddings_directory = _resolve_path(
        base, config.paths.embeddings_directory
    )

    config.recommendation.random_seed = config.random_seed

    return config
