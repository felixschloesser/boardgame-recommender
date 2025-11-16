from dataclasses import dataclass
from pathlib import Path

import tomllib


@dataclass
class PathsConfig:
    raw_data: Path
    processed_features: Path
    models_directory: Path


@dataclass
class FeaturesConfig:
    text_columns: list[str]
    numeric_columns: list[str]


@dataclass
class LoggingConfig:
    level: str


@dataclass
class PreprocessingConfig:
    top_record_limit: int | None


@dataclass
class SingularValueDecompositionConfig:
    component_count: int
    random_state: int
    minimum_document_frequency: int
    maximum_features: int


@dataclass
class Config:
    paths: PathsConfig
    features: FeaturesConfig
    logging: LoggingConfig
    preprocessing: PreprocessingConfig
    singular_value_decomposition: SingularValueDecompositionConfig


def _resolve_path(base_directory: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_directory / path).resolve()


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from ``config.toml`` or the provided path."""

    if path is None:
        config_path = Path.cwd() / "config.toml"
    else:
        config_path = Path(path)

    with config_path.open("rb") as config_file:
        raw_config = tomllib.load(config_file)

    config_directory = config_path.parent

    raw_paths_config = raw_config.get("paths", {})
    raw_models_directory = raw_paths_config.get(
        "models_dir", raw_paths_config.get("artifacts")
    )
    if raw_models_directory is None:
        raise KeyError("Config.paths must provide 'models_dir' (or legacy 'artifacts')")

    paths = PathsConfig(
        raw_data=_resolve_path(config_directory, raw_paths_config["raw_data"]),
        processed_features=_resolve_path(
            config_directory, raw_paths_config["processed_features"]
        ),
        models_directory=_resolve_path(config_directory, raw_models_directory),
    )

    raw_features = raw_config.get("features", {})
    features = FeaturesConfig(
        text_columns=list(raw_features.get("text_columns", [])),
        numeric_columns=list(raw_features.get("numeric_columns", [])),
    )

    raw_logging = raw_config.get("logging", {})
    logging_config = LoggingConfig(level=raw_logging.get("level", "INFO"))

    raw_preprocessing = raw_config.get("preprocessing", {})
    preprocessing = PreprocessingConfig(
        top_record_limit=raw_preprocessing.get("top_n", 2000)
    )

    raw_svd_config = raw_config.get("svd", {})
    singular_value_decomposition = SingularValueDecompositionConfig(
        component_count=raw_svd_config.get("n_components"),
        random_state=raw_svd_config.get("random_state"),
        minimum_document_frequency=raw_svd_config.get("min_df"),
        maximum_features=raw_svd_config.get("max_features"),
    )

    return Config(
        paths=paths,
        features=features,
        logging=logging_config,
        preprocessing=preprocessing,
        singular_value_decomposition=singular_value_decomposition,
    )
