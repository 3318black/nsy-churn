"""Tests of the model training, its selection and its serialisation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from churn.config import AppConfig, FeatureMappingEntry, FeatureSource, load_feature_mapping
from churn.data.synthetic import generate_dataset
from churn.evaluation.protocol import evaluate_scorers
from churn.evaluation.splitting import temporal_folds
from churn.features.build import GridSpec, TrainingSet, build_training_set
from churn.features.catalog import family_of
from churn.models.registry import METADATA_FILE, TrainedModel, load_model, save_model
from churn.models.train import (
    BoosterParams,
    ModelIdentity,
    SelectionSettings,
    TrainingSettings,
    XGBoostScorer,
    param_candidates,
    select_params,
    train_model,
)

#: Two small combinations, so the tests stay fast.
SMALL = (
    BoosterParams(max_depth=2, n_estimators=20, learning_rate=0.3),
    BoosterParams(max_depth=3, n_estimators=40, learning_rate=0.1),
)

IDENTITY = ModelIdentity(project_version="0.0.0", source_label="synthetic test", is_synthetic=True)


@pytest.fixture(scope="module")
def training(config: AppConfig) -> TrainingSet:
    """Build a small synthetic training set."""
    profile = config.sources.synthetic.model_copy(update={"n_accounts": 300})
    dataset = generate_dataset(profile, seed=config.project.random_seed, resolution="us")
    spec = GridSpec(
        horizon_days=profile.horizon_days,
        min_account_age_days=config.business.min_account_age_days,
        min_history_days=config.features.min_history_days,
        observation_frequency=config.features.observation_frequency,
        windows_days=tuple(config.features.windows_days),
        resolution="us",
    )
    return build_training_set(dataset, spec)


@pytest.fixture(scope="module")
def settings(config: AppConfig) -> SelectionSettings:
    """Selection settings of the synthetic profile."""
    return SelectionSettings(
        k=config.business.weekly_capacity_k,
        frequency=config.evaluation.scoring_period,
        horizon_days=config.sources.synthetic.horizon_days,
        embargo_days=config.sources.synthetic.embargo_days,
        seed=config.project.random_seed,
    )


@pytest.fixture(scope="module")
def mapping(config: AppConfig) -> dict[str, FeatureMappingEntry]:
    """The business mapping of the repository."""
    return load_feature_mapping(config.paths.feature_mapping)


@pytest.fixture(scope="module")
def model(
    training: TrainingSet, settings: SelectionSettings, mapping: dict[str, FeatureMappingEntry]
) -> TrainedModel:
    """Train one model for the tests that only read it."""
    return train_model(training, TrainingSettings(SMALL, settings, 0.75), IDENTITY, mapping)


def test_the_candidates_cover_the_whole_configured_grid(config: AppConfig) -> None:
    """The reduced grid of D16 is taken whole, each combination once."""
    grid = config.model.param_grid
    candidates = param_candidates(grid)
    assert len(candidates) == len(grid.max_depth) * len(grid.n_estimators) * len(grid.learning_rate)
    assert len(set(candidates)) == len(candidates)


def test_selection_measures_every_candidate_and_keeps_the_best(
    training: TrainingSet, settings: SelectionSettings
) -> None:
    """The choice is the best Precision@K on the inner validation."""
    selection = select_params(training, SMALL, settings)
    assert selection.fallback_reason == ""
    assert len(selection.scores) == len(SMALL)
    best = int(selection.scores["precision_at_k"].to_numpy().argmax())
    assert selection.params == SMALL[best]


def test_a_selection_without_two_classes_falls_back_loudly(
    training: TrainingSet, settings: SelectionSettings
) -> None:
    """Nothing to measure is said, not hidden behind a default."""
    negatives = training._replace(target=training.target * 0)
    selection = select_params(negatives, SMALL, settings)
    assert selection.params == SMALL[0]
    assert "single class" in selection.fallback_reason


def test_the_scorer_selects_inside_every_fold(
    training: TrainingSet, settings: SelectionSettings, config: AppConfig
) -> None:
    """Each fold chooses on its own training rows, never on its test period."""
    profile = config.sources.synthetic
    folds = temporal_folds(training.grid["T0"], 2, profile.horizon_days, profile.embargo_days)
    scorer = XGBoostScorer(SMALL, settings)
    result = evaluate_scorers(training, folds, [scorer], k=settings.k, frequency=settings.frequency)
    assert len(result.folds) == len(folds)
    assert len(scorer.selections) == len(folds)


def test_a_family_restricted_scorer_never_sees_the_other_families(
    training: TrainingSet, settings: SelectionSettings
) -> None:
    """The model gain is measured on the same features as the logistic one."""
    families = {FeatureSource.FINANCE, FeatureSource.GENERAL}
    scorer = XGBoostScorer(SMALL, settings, families=families, name="xgboost_finance")
    scorer.fit_score(training, training.features.head(10), training.grid.head(10))
    assert scorer.classifier is not None
    names = scorer.classifier.get_booster().feature_names
    assert names
    assert {family_of(name) for name in names} <= families


def test_training_is_reproducible(
    model: TrainedModel,
    training: TrainingSet,
    settings: SelectionSettings,
    mapping: dict[str, FeatureMappingEntry],
) -> None:
    """Same data, same settings, same version and same scores."""
    again = train_model(training, TrainingSettings(SMALL, settings, 0.75), IDENTITY, mapping)
    assert again.metadata.model_version == model.metadata.model_version
    assert np.array_equal(again.score(training.features), model.score(training.features))


def test_a_reloaded_model_scores_exactly_the_same(
    model: TrainedModel, training: TrainingSet, tmp_path: Path
) -> None:
    """Criterion 5 of lot 5: an export can be reproduced from the saved model."""
    reloaded = load_model(save_model(model, tmp_path))
    assert np.array_equal(reloaded.score(training.features), model.score(training.features))
    assert reloaded.metadata == model.metadata


def test_the_threshold_is_computed_and_serialised(model: TrainedModel, tmp_path: Path) -> None:
    """Criterion 4 of lot 5: measured at training time, never written in the code."""
    assert model.metadata.significance_threshold > 0
    folder = save_model(model, tmp_path)
    payload = json.loads((folder / METADATA_FILE).read_text(encoding="utf-8"))
    assert payload["significance_threshold"] == model.metadata.significance_threshold
    assert payload["significance_quantile"] == 0.75
    assert payload["is_synthetic"] is True


def test_scoring_refuses_a_frame_missing_a_feature(
    model: TrainedModel, training: TrainingSet
) -> None:
    """A silently reordered or truncated matrix would score garbage."""
    with pytest.raises(ValueError, match="needs 1 features"):
        model.score(training.features.drop(columns=training.features.columns[0]))


def test_infinite_values_are_scored_as_missing(model: TrainedModel, training: TrainingSet) -> None:
    """XGBoost refuses infinities, measured, so they must not reach it."""
    features = training.features.head(5).copy()
    features.iloc[0, 0] = np.inf
    assert np.isfinite(model.score(features)).all()


def test_training_refuses_a_single_class(
    training: TrainingSet, settings: SelectionSettings, mapping: dict[str, FeatureMappingEntry]
) -> None:
    """Nothing can be learned, so nothing is saved."""
    negatives = training._replace(target=training.target * 0)
    with pytest.raises(ValueError, match="single class"):
        train_model(negatives, TrainingSettings(SMALL, settings, 0.75), IDENTITY, mapping)


def test_training_refuses_an_origin_without_label(
    training: TrainingSet, settings: SelectionSettings, mapping: dict[str, FeatureMappingEntry]
) -> None:
    """A model able to print a technical name as a reason is not saved."""
    partial = {name: entry for name, entry in mapping.items() if name != "mrr"}
    with pytest.raises(ValueError, match="mrr"):
        train_model(training, TrainingSettings(SMALL, settings, 0.75), IDENTITY, partial)
