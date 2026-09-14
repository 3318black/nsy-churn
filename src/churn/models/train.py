"""Training of the gradient boosted model, decisions D12 and D23.

Two rules matter more than the model itself.

Selection never sees the test period
    The hyperparameters are chosen on an inner chronological split of the
    training rows alone, cut with the same embargo and purge as the outer folds,
    by the generic selection of :mod:`churn.evaluation.selection`. Choosing them
    on the test folds would turn the evaluation into a selection, and the
    reported Precision@K into the best of many draws.
The grid reaches simple models
    The grid of decision D16 was cut short by a deadline, and the selection kept
    landing in its most cautious corner. Decision D23 widens it towards shallower
    and smaller models, so that corner is no longer a wall.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import xgboost as xgb

from churn.config import FeatureMappingEntry, FeatureSource, ParamGridConfig
from churn.evaluation.selection import Selection, SelectionSettings, select_candidate
from churn.features.build import TrainingSet
from churn.features.catalog import family_of, select_families
from churn.models.explain import (
    aggregate_by_origin,
    check_mapping,
    feature_contributions,
    significance_threshold,
)
from churn.models.registry import (
    ModelMetadata,
    TrainedModel,
    as_model_input,
    training_fingerprint,
)

__all__ = [
    "THRESHOLD_SAMPLE_ROWS",
    "BoosterParams",
    "ModelIdentity",
    "Selection",
    "SelectionSettings",
    "TrainingSettings",
    "XGBoostScorer",
    "fit_classifier",
    "param_candidates",
    "select_params",
    "train_model",
]

logger = logging.getLogger(__name__)

#: Classes a classifier needs to learn anything.
_BINARY_CLASSES = 2

#: Training rows the significance threshold is computed on. A quantile does not
#: need every row, and the contributions of several hundred thousand rows cost
#: minutes. The sample is drawn with the training seed.
THRESHOLD_SAMPLE_ROWS = 50_000


@dataclass(frozen=True, slots=True)
class BoosterParams:
    """One combination of the hyperparameter grid."""

    max_depth: int
    n_estimators: int
    learning_rate: float


def param_candidates(grid: ParamGridConfig) -> tuple[BoosterParams, ...]:
    """Return every combination of the configured grid, in a fixed order."""
    return tuple(
        BoosterParams(max_depth=depth, n_estimators=trees, learning_rate=rate)
        for depth, trees, rate in itertools.product(
            grid.max_depth, grid.n_estimators, grid.learning_rate
        )
    )


def fit_classifier(
    features: pd.DataFrame, target: pd.Series, params: BoosterParams, seed: int
) -> xgb.XGBClassifier:
    """Fit one classifier. Two fits with the same inputs yield the same trees."""
    classifier = xgb.XGBClassifier(
        n_estimators=params.n_estimators,
        max_depth=params.max_depth,
        learning_rate=params.learning_rate,
        objective="binary:logistic",
        tree_method="hist",
        random_state=seed,
    )
    classifier.fit(as_model_input(features), target.to_numpy())
    return classifier


def select_params(
    training: TrainingSet,
    candidates: Sequence[BoosterParams],
    settings: SelectionSettings,
) -> Selection[BoosterParams]:
    """Choose the hyperparameters on an inner split of the training rows.

    The generic selection of :mod:`churn.evaluation.selection` does the cutting
    and the measuring; this function only says how a booster fits and scores.

    Args:
        training: grid, target and features of the training rows only.
        candidates: the combinations to compare.
        settings: what the measurement needs.

    Returns:
        The chosen combination and the measure of every candidate.
    """

    def score(params: BoosterParams, inner: TrainingSet, validation: pd.DataFrame) -> np.ndarray:
        classifier = fit_classifier(inner.features, inner.target, params, settings.seed)
        return classifier.predict_proba(as_model_input(validation))[:, 1]

    return select_candidate(training, candidates, settings, score, asdict)


class XGBoostScorer:
    """Gradient boosted trees, tuned inside each fold on its training rows."""

    def __init__(
        self,
        candidates: Sequence[BoosterParams],
        settings: SelectionSettings,
        families: Collection[FeatureSource] | None = None,
        name: str = "xgboost",
    ) -> None:
        """Initialise the scorer.

        Args:
            candidates: the hyperparameter combinations to choose from.
            settings: what the inner selection needs.
            families: feature families to learn from, all of them when ``None``.
            name: name the scorer is reported under.
        """
        self._candidates = tuple(candidates)
        self._settings = settings
        self._families = families
        self.name = name
        self.selections: list[Selection] = []
        self.classifier: xgb.XGBClassifier | None = None

    def fit_score(
        self,
        train: TrainingSet,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Select, fit on the training rows, and score the test rows."""
        del test_grid
        if train.target.nunique() < _BINARY_CLASSES:
            logger.warning("training fold holds a single class, constant scores returned")
            self.classifier = None
            return np.zeros(len(test_features))

        if self._families is not None:
            train = train._replace(features=select_families(train.features, self._families))
            test_features = select_families(test_features, self._families)

        selection = select_params(train, self._candidates, self._settings)
        self.selections.append(selection)
        self.classifier = fit_classifier(
            train.features, train.target, selection.params, self._settings.seed
        )
        return self.classifier.predict_proba(as_model_input(test_features))[:, 1]


@dataclass(frozen=True, slots=True)
class TrainingSettings:
    """How the final model is trained.

    Attributes:
        candidates: the hyperparameter combinations to choose from.
        selection: what the inner selection needs.
        significance_quantile: quantile the threshold is taken at, D7.
        families: feature families to learn from, all of them when ``None``.
    """

    candidates: tuple[BoosterParams, ...]
    selection: SelectionSettings
    significance_quantile: float
    families: frozenset[FeatureSource] | None = None


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Where a model comes from, written into its metadata.

    Attributes:
        project_version: version of the project, prefix of the model version.
        source_label: label of the data source.
        is_synthetic: whether the data is simulated.
    """

    project_version: str
    source_label: str
    is_synthetic: bool


def train_model(
    training: TrainingSet,
    settings: TrainingSettings,
    identity: ModelIdentity,
    mapping: Mapping[str, FeatureMappingEntry],
) -> TrainedModel:
    """Train the final model on every row of the grid.

    Args:
        training: the whole training set.
        settings: how to train.
        identity: where the model comes from.
        mapping: the business mapping, checked before anything is saved.

    Returns:
        The fitted model and its metadata.

    Raises:
        ValueError: when the grid holds a single class, or when an origin
            variable of the model has no business label.
    """
    if training.target.nunique() < _BINARY_CLASSES:
        message = "the training set holds a single class, nothing can be learned"
        raise ValueError(message)

    features = (
        training.features
        if settings.families is None
        else select_families(training.features, settings.families)
    )
    scoped = training._replace(features=features)
    selection = select_params(scoped, settings.candidates, settings.selection)
    seed = settings.selection.seed
    classifier = fit_classifier(features, training.target, selection.params, seed)

    sample = (
        features.sample(n=THRESHOLD_SAMPLE_ROWS, random_state=seed)
        if len(features) > THRESHOLD_SAMPLE_ROWS
        else features
    )
    aggregated = aggregate_by_origin(feature_contributions(classifier, as_model_input(sample)))
    check_mapping(aggregated.columns, mapping)
    threshold = significance_threshold(aggregated, settings.significance_quantile)

    fingerprint = training_fingerprint(features, training.target)
    params = asdict(selection.params)
    version_digest = hashlib.sha256(
        json.dumps(
            {"data": fingerprint, "params": params, "seed": seed, "features": list(features)},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    metadata = ModelMetadata(
        model_version=f"{identity.project_version}-{version_digest[:12]}",
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        seed=seed,
        params=params,
        feature_names=tuple(features.columns),
        families=tuple(sorted({family_of(column).value for column in features.columns})),
        significance_quantile=settings.significance_quantile,
        significance_threshold=threshold,
        training_fingerprint=fingerprint,
        training_rows=len(features),
        training_positives=int(training.target.sum()),
        source_label=identity.source_label,
        is_synthetic=identity.is_synthetic,
    )
    logger.info(
        "model trained",
        extra={
            "version": metadata.model_version,
            "params": params,
            "threshold": threshold,
            "selection_fallback": selection.fallback_reason,
        },
    )
    return TrainedModel(classifier=classifier, metadata=metadata)
