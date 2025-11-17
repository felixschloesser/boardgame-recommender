# config.py

from pathlib import Path
from typing import List, Tuple
from pydantic import BaseModel, Field, model_validator
import tomllib


# --------------------------------------
# PATH CONFIG
# --------------------------------------


class PathsConfig(BaseModel):
    raw_data_directory: Path
    domain_stopwords_file: Path
    processed_features_file: Path
    embeddings_directory: Path


# --------------------------------------
# FEATURES CONFIG
# --------------------------------------


class TextFeatureConfig(BaseModel):
    columns: List[str]


class CategoricalFeatureConfig(BaseModel):
    columns: List[str]


class NormalNumericFeatureConfig(BaseModel):
    columns: List[str]
    normalization_strategy: str


class HeavyTailedNumericFeatureConfig(BaseModel):
    columns: List[str]
    normalization_strategy: str


class NumericFeatureConfig(BaseModel):
    normal: NormalNumericFeatureConfig
    heavy_tail: HeavyTailedNumericFeatureConfig


class FeatureWeightsConfig(BaseModel):
    description: float
    mechanics: float
    categories: float
    themes: float
    numeric: float


class FeaturesConfig(BaseModel):
    text: TextFeatureConfig
    categorical: CategoricalFeatureConfig
    numeric: NumericFeatureConfig
    weights: FeatureWeightsConfig


# --------------------------------------
# TOKENIZATION
# --------------------------------------


class TokenizationConfig(BaseModel):
    vocabulary_deduplication: bool
    remove_english_stopwords: bool
    allowed_stopwords: List[str]
    remove_domain_stopwords: bool
    ngram_range: Tuple[int, int]


# --------------------------------------
# PREPROCESSING CONFIG
# --------------------------------------


class PreprocessingConfig(BaseModel):
    cutoff_metric: str
    cutoff_quantile: float = Field(ge=0.0, le=1.0)
    features: FeaturesConfig
    tokenization: TokenizationConfig


# --------------------------------------
# TRAINING CONFIG
# --------------------------------------


class SVDTrainingConfig(BaseModel):
    tag_vectorization_strategy: str
    text_vectorization_strategy: str
    latent_dimension_strategy: str
    latent_dimensions: int
    normalization_strategy: str
    iterations: int


class TFIDFTrainingConfig(BaseModel):
    min_document_occurences: int
    max_document_frequency: float
    max_features: int
    normalization_strategy: str
    sublinear: bool


class TrainingConfig(BaseModel):
    show_progress: bool
    svd: SVDTrainingConfig
    tfidf: TFIDFTrainingConfig  # FIXED: use snake_case, not "tf-idf"


# --------------------------------------
# RECOMMENDATION
# --------------------------------------


class RecommendationConfig(BaseModel):
    preferences_vectorization_strategy: str
    num_centroids: int
    min_cluster_size: int


# --------------------------------------
# LOGGING + RANDOM SEED
# --------------------------------------


class LoggingConfig(BaseModel):
    level: str


# --------------------------------------
# TOP-LEVEL CONFIG
# --------------------------------------


class Config(BaseModel):
    random: dict
    logging: LoggingConfig
    paths: PathsConfig
    preprocessing: PreprocessingConfig
    training: TrainingConfig
    recommendation: RecommendationConfig

    @model_validator(mode="after")
    def resolve_relative_paths(self):
        """
        Converts all relative paths to absolute paths based on the config file location.
        """
        base = Path(self.__config_file_dir)  # set dynamically in loader

        self.paths.raw_data_directory = base / self.paths.raw_data_directory
        self.paths.domain_stopwords_file = base / self.paths.domain_stopwords_file
        self.paths.processed_features_file = base / self.paths.processed_features_file
        self.paths.embeddings_directory = base / self.paths.embeddings_directory

        return self


# --------------------------------------
# LOAD FUNCTION
# --------------------------------------


def load_config(path: str) -> Config:
    path = Path(path)
    data = tomllib.loads(path.read_text("utf-8"))

    # Inject config directory into instance for model validator
    config = Config.model_validate(data)
    config.__config_file_dir = str(path.parent)

    # Re-run validator now that the directory is available
    return config.resolve_relative_paths()
