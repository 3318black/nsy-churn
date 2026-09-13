"""Serialisation of a trained model, with what makes it traceable.

A score file travels without the model that produced it. When a figure is
questioned months later, the metadata saved next to the model answers the
questions that matter: which data it was trained on, with which settings, and
which significance threshold filters its factors.

The model is saved in XGBoost's binary format. Reloading it yields exactly the
same scores, checked by a test, which is what lets an export be reproduced.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from churn.models.explain import feature_contributions

__all__ = [
    "METADATA_FILE",
    "MODEL_FILE",
    "ModelMetadata",
    "TrainedModel",
    "as_model_input",
    "load_model",
    "save_model",
    "training_fingerprint",
]

#: File holding the trees.
MODEL_FILE = "model.ubj"

#: File holding the metadata.
METADATA_FILE = "metadata.json"


def as_model_input(features: pd.DataFrame) -> pd.DataFrame:
    """Return the features as the model reads them.

    XGBoost 3.4 refuses infinities, measured on 2026-09-13. A trend over a zero
    denominator can produce one. It becomes a missing value, which the trees
    route natively, rather than a zero that would claim a fact.

    Args:
        features: the feature matrix.

    Returns:
        A float copy with every infinity replaced by ``NaN``.
    """
    values = features.to_numpy(dtype="float64", copy=True)
    values[~np.isfinite(values)] = np.nan
    return pd.DataFrame(values, index=features.index, columns=features.columns)


def training_fingerprint(features: pd.DataFrame, target: pd.Series) -> str:
    """Return a digest of the exact training data.

    Two models trained on the same rows share it; a single changed value changes
    it.

    Args:
        features: the training features.
        target: the training target.

    Returns:
        A hexadecimal SHA-256 digest.
    """
    digest = hashlib.sha256()
    digest.update("\x1f".join(features.columns).encode("utf-8"))
    digest.update(pd.util.hash_pandas_object(features, index=False).to_numpy().tobytes())
    digest.update(pd.util.hash_pandas_object(target, index=False).to_numpy().tobytes())
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """What a saved model carries besides its trees.

    Attributes:
        model_version: identifier written on every exported row.
        created_at: training time, ISO 8601, UTC.
        seed: seed of the training.
        params: chosen hyperparameters.
        feature_names: features, in the order the model reads them.
        families: feature families the model learned from.
        significance_quantile: quantile the threshold was taken at.
        significance_threshold: threshold a contribution must exceed to be shown.
        training_fingerprint: digest of the training data.
        training_rows: number of training rows.
        training_positives: number of positive training rows.
        source_label: label of the data source.
        is_synthetic: whether the data was simulated. Decision D2.
    """

    model_version: str
    created_at: str
    seed: int
    params: dict[str, float]
    feature_names: tuple[str, ...]
    families: tuple[str, ...]
    significance_quantile: float
    significance_threshold: float
    training_fingerprint: str
    training_rows: int
    training_positives: int
    source_label: str
    is_synthetic: bool

    def to_json(self) -> str:
        """Return the metadata as indented JSON."""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> ModelMetadata:
        """Rebuild the metadata from its JSON form."""
        payload = json.loads(text)
        payload["feature_names"] = tuple(payload["feature_names"])
        payload["families"] = tuple(payload["families"])
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class TrainedModel:
    """A fitted classifier and its metadata.

    Attributes:
        classifier: the fitted XGBoost classifier.
        metadata: what makes it traceable.
    """

    classifier: xgb.XGBClassifier
    metadata: ModelMetadata

    def _aligned(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return the features in the order the model reads them."""
        expected = list(self.metadata.feature_names)
        missing = [name for name in expected if name not in features.columns]
        if missing:
            message = (
                f"model {self.metadata.model_version} needs {len(missing)} features the "
                f"frame does not hold, first ones: {missing[:5]}"
            )
            raise ValueError(message)
        return as_model_input(features.loc[:, expected])

    def score(self, features: pd.DataFrame) -> np.ndarray:
        """Return the raw score of each row. Not a calibrated probability, D6."""
        return self.classifier.predict_proba(self._aligned(features))[:, 1]

    def contributions(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return the native contribution of every feature, bias excluded."""
        return feature_contributions(self.classifier, self._aligned(features))


def save_model(model: TrainedModel, directory: Path) -> Path:
    """Save the trees and the metadata under a folder named after the version.

    Args:
        model: the model to save.
        directory: parent directory, from ``paths.models``.

    Returns:
        The folder the model was written to.
    """
    target = directory / model.metadata.model_version
    target.mkdir(parents=True, exist_ok=True)
    model.classifier.save_model(target / MODEL_FILE)
    (target / METADATA_FILE).write_text(model.metadata.to_json(), encoding="utf-8")
    return target


def load_model(folder: Path) -> TrainedModel:
    """Reload a model saved by :func:`save_model`.

    Args:
        folder: the folder returned by :func:`save_model`.

    Returns:
        The model, scoring exactly as it did before being saved.
    """
    classifier = xgb.XGBClassifier()
    classifier.load_model(folder / MODEL_FILE)
    metadata = ModelMetadata.from_json((folder / METADATA_FILE).read_text(encoding="utf-8"))
    return TrainedModel(classifier=classifier, metadata=metadata)
