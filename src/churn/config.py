"""Typed loading of the project configuration.

Two YAML files are covered: ``config/config.yaml``, the project settings, and
``config/feature_mapping.yaml``, the static translation from technical feature
names to business labels.

Three rules drive this module.

1. No silent default. Every key declared in the YAML files is mandatory, and a
   missing key raises :class:`ConfigError` naming the offending key. Falling
   back to a hardcoded value would move a business parameter into the code,
   which ``AGENTS.md`` section 7 forbids.
2. Cross validation at load time. For every source profile ``embargo_days``
   must be greater than or equal to ``horizon_days``. A shorter embargo lets
   the training target resolve inside the test period, which decision D4
   rules out.
3. Paths are exposed as :class:`~pathlib.Path` objects resolved against the
   project root, so that no module ever builds a file path on its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

__all__ = [
    "PROJECT_ROOT",
    "AppConfig",
    "BusinessConfig",
    "ConfigError",
    "EvaluationConfig",
    "ExportConfig",
    "FeatureMappingEntry",
    "FeatureSource",
    "FeaturesConfig",
    "KkboxRawFiles",
    "KkboxSourceConfig",
    "ModelConfig",
    "ParamGridConfig",
    "PathsConfig",
    "ProjectConfig",
    "SourceProfile",
    "SourcesConfig",
    "SyntheticSourceConfig",
    "load_config",
    "load_feature_mapping",
]

#: Repository root, derived from the location of this file (``src/churn``).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Key used to pass the project root through the Pydantic validation context.
PROJECT_ROOT_CONTEXT_KEY = "project_root"

_DEFAULT_CONFIG_RELATIVE_PATH = Path("config") / "config.yaml"


class ConfigError(RuntimeError):
    """Raised when a configuration file is missing, malformed or inconsistent."""


class FeatureSource(StrEnum):
    """Business family a feature belongs to, used as a label prefix."""

    SUPPORT = "SUPPORT"
    PRODUCT = "PRODUCT"
    FINANCE = "FINANCE"
    COMMERCIAL = "COMMERCIAL"
    GENERAL = "GENERAL"


class _StrictModel(BaseModel):
    """Base model that refuses unknown keys and forbids mutation after loading."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(_StrictModel):
    """Project identity and global randomness seed."""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    random_seed: int


class SourceProfile(_StrictModel):
    """Fields shared by every data source profile."""

    label: str = Field(min_length=1)
    is_synthetic: bool
    horizon_days: int = Field(gt=0)
    embargo_days: int = Field(ge=0)


class KkboxRawFiles(_StrictModel):
    """File names of the raw KKBox extracts, relative to ``paths.raw``."""

    members: str = Field(min_length=1)
    transactions: str = Field(min_length=1)
    user_logs: str = Field(min_length=1)
    official_labels: str = Field(min_length=1)


class KkboxSourceConfig(SourceProfile):
    """KKBox profile, which carries the demonstration and every measurement."""

    sample_accounts: int = Field(gt=0)
    chunk_size: int = Field(gt=0)
    raw_files: KkboxRawFiles

    @field_validator("is_synthetic")
    @classmethod
    def _reject_synthetic_flag(cls, value: bool) -> bool:
        if value:
            message = "the kkbox profile describes a real dataset, is_synthetic must be false"
            raise ValueError(message)
        return value


class SyntheticSourceConfig(SourceProfile):
    """Synthetic profile, which serves the automated tests and never the demo."""

    n_accounts: int = Field(gt=0)
    history_start: date
    history_end: date
    annual_churn_rate: float = Field(gt=0.0, le=1.0)
    unpredictable_churn_share: float = Field(ge=0.0, le=1.0)
    missing_data_rate: float = Field(ge=0.0, le=1.0)
    duplicate_timestamp_rate: float = Field(ge=0.0, le=1.0)

    @field_validator("is_synthetic")
    @classmethod
    def _require_synthetic_flag(cls, value: bool) -> bool:
        if not value:
            message = "the synthetic profile is generated locally, is_synthetic must be true"
            raise ValueError(message)
        return value

    @model_validator(mode="after")
    def _check_history_window(self) -> Self:
        if self.history_end <= self.history_start:
            message = (
                f"history_end ({self.history_end}) must be strictly after "
                f"history_start ({self.history_start})"
            )
            raise ValueError(message)
        return self


class SourcesConfig(_StrictModel):
    """Declared source profiles. Both are mandatory, see decision D14."""

    kkbox: KkboxSourceConfig
    synthetic: SyntheticSourceConfig

    def as_mapping(self) -> Mapping[str, SourceProfile]:
        """Return the profiles keyed by their configuration name."""
        return {name: getattr(self, name) for name in type(self).model_fields}


class BusinessConfig(_StrictModel):
    """Business rules shared by every source."""

    min_account_age_days: int = Field(ge=0)
    weekly_capacity_k: int = Field(gt=0)
    top_factors: int = Field(gt=0)


class FeaturesConfig(_StrictModel):
    """Shape of the training grid and of the rolling windows."""

    observation_frequency: str = Field(min_length=1)
    windows_days: list[int] = Field(min_length=1)
    min_history_days: int = Field(gt=0)
    datetime_resolution: Literal["s", "ms", "us", "ns"]

    @field_validator("windows_days")
    @classmethod
    def _require_positive_windows(cls, value: list[int]) -> list[int]:
        if any(window <= 0 for window in value):
            message = f"every window must be a positive number of days, got {value}"
            raise ValueError(message)
        return value


class EvaluationConfig(_StrictModel):
    """Evaluation protocol, see decisions D4 and D5."""

    n_splits: int = Field(gt=0)
    scoring_period: str = Field(min_length=1)


class ParamGridConfig(_StrictModel):
    """Reduced hyperparameter grid, deliberately small, see decision D16."""

    max_depth: list[int] = Field(min_length=1)
    n_estimators: list[int] = Field(min_length=1)
    learning_rate: list[float] = Field(min_length=1)


class ModelConfig(_StrictModel):
    """Model family and the settings of its search."""

    algorithm: str = Field(min_length=1)
    significance_quantile: float = Field(gt=0.0, lt=1.0)
    param_grid: ParamGridConfig


class ExportConfig(_StrictModel):
    """Output format of the exported files, see decision D8."""

    csv_encoding: str = Field(min_length=1)
    csv_separator: str = Field(min_length=1, max_length=1)
    max_label_length: int = Field(gt=0)


class PathsConfig(_StrictModel):
    """Directories and files of the project, resolved against the project root."""

    raw: Path
    processed: Path
    exports: Path
    models: Path
    reports: Path
    feature_mapping: Path

    @field_validator("*", mode="after")
    @classmethod
    def _resolve_against_project_root(cls, value: Path, info: ValidationInfo) -> Path:
        if value.is_absolute():
            return value
        context = info.context if isinstance(info.context, Mapping) else {}
        root = context.get(PROJECT_ROOT_CONTEXT_KEY, PROJECT_ROOT)
        return Path(root, value)


class AppConfig(_StrictModel):
    """Whole content of ``config/config.yaml``, validated."""

    project: ProjectConfig
    active_source: str = Field(min_length=1)
    sources: SourcesConfig
    business: BusinessConfig
    features: FeaturesConfig
    evaluation: EvaluationConfig
    model: ModelConfig
    export: ExportConfig
    paths: PathsConfig

    @model_validator(mode="after")
    def _check_active_source_is_declared(self) -> Self:
        known = tuple(self.sources.as_mapping())
        if self.active_source not in known:
            message = (
                f"active_source '{self.active_source}' does not match any profile of "
                f"sources; declared profiles: {', '.join(known)}"
            )
            raise ValueError(message)
        return self

    @model_validator(mode="after")
    def _check_embargo_covers_horizon(self) -> Self:
        offenders = [
            f"profile '{name}': embargo_days ({profile.embargo_days}) is lower than "
            f"horizon_days ({profile.horizon_days})"
            for name, profile in self.sources.as_mapping().items()
            if profile.embargo_days < profile.horizon_days
        ]
        if offenders:
            message = (
                "embargo_days must be greater than or equal to horizon_days for every "
                "source profile, otherwise the training target resolves inside the test "
                "period, see decision D4; " + "; ".join(offenders)
            )
            raise ValueError(message)
        return self

    def active_profile(self) -> SourceProfile:
        """Return the profile designated by ``active_source``.

        Raises:
            ConfigError: if ``active_source`` matches no declared profile.
        """
        profiles = self.sources.as_mapping()
        try:
            return profiles[self.active_source]
        except KeyError as error:
            message = (
                f"active_source '{self.active_source}' does not match any profile of "
                f"sources; declared profiles: {', '.join(profiles)}"
            )
            raise ConfigError(message) from error


class FeatureMappingEntry(_StrictModel):
    """One line of ``config/feature_mapping.yaml``.

    ``action`` may be an empty string for a structural feature on which no
    commercial action is possible, but it is never absent.
    """

    label: str = Field(min_length=1)
    source: FeatureSource
    action: str


_FEATURE_MAPPING_ADAPTER: TypeAdapter[dict[str, FeatureMappingEntry]] = TypeAdapter(
    dict[str, FeatureMappingEntry]
)


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read a YAML file and return its top level mapping."""
    if not path.is_file():
        message = f"configuration file not found: {path}"
        raise ConfigError(message)
    try:
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except yaml.YAMLError as error:
        message = f"invalid YAML in {path}: {error}"
        raise ConfigError(message) from error
    if not isinstance(payload, dict):
        message = f"the top level of {path} must be a mapping, got {type(payload).__name__}"
        raise ConfigError(message)
    return payload


def _format_validation_error(path: Path, error: ValidationError) -> str:
    """Turn a Pydantic error into a message naming every offending key."""
    lines = [f"invalid configuration in {path}:"]
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        lines.append(f"  - {location}: {item['msg']}")
    return "\n".join(lines)


def load_config(path: Path | None = None, *, project_root: Path | None = None) -> AppConfig:
    """Load and validate ``config/config.yaml``.

    Args:
        path: configuration file to read. Defaults to ``config/config.yaml``
            under the project root.
        project_root: root the relative paths of the ``paths`` section are
            resolved against. Defaults to the repository root.

    Returns:
        The validated configuration.

    Raises:
        ConfigError: if the file is missing, malformed, incomplete or
            inconsistent. The message names the offending keys.
    """
    root = PROJECT_ROOT if project_root is None else project_root
    config_path = root / _DEFAULT_CONFIG_RELATIVE_PATH if path is None else path
    payload = _read_yaml_mapping(config_path)
    try:
        return AppConfig.model_validate(payload, context={PROJECT_ROOT_CONTEXT_KEY: root})
    except ValidationError as error:
        raise ConfigError(_format_validation_error(config_path, error)) from error


def load_feature_mapping(path: Path) -> dict[str, FeatureMappingEntry]:
    """Load and validate the technical to business feature mapping.

    The path is never built here. It comes from ``config.paths.feature_mapping``.

    Args:
        path: the ``feature_mapping.yaml`` file to read.

    Returns:
        The entries keyed by original feature name, before any encoding.

    Raises:
        ConfigError: if the file is missing, malformed or holds an entry outside
            the nomenclature. The message names the offending entries.
    """
    payload = _read_yaml_mapping(path)
    try:
        return _FEATURE_MAPPING_ADAPTER.validate_python(payload)
    except ValidationError as error:
        raise ConfigError(_format_validation_error(path, error)) from error
