"""Tests of the generic selection and of the tuned logistic baseline, decision D23."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from churn.config import AppConfig, ConfigError, FeatureSource, load_config
from churn.data.synthetic import generate_dataset
from churn.evaluation.baselines import TunedLogisticScorer, signed_log1p
from churn.evaluation.protocol import evaluate_scorers
from churn.evaluation.selection import SelectionSettings, select_candidate
from churn.evaluation.splitting import temporal_folds
from churn.features.build import GridSpec, TrainingSet, build_training_set
from churn.features.catalog import select_families


@pytest.fixture(scope="module")
def training(config: AppConfig) -> TrainingSet:
    """A small synthetic training set."""
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


def test_signed_log1p_compresses_and_keeps_the_sign() -> None:
    """Nine becomes log(10), minus nine its opposite, zero stays zero."""
    values = signed_log1p(np.array([-9.0, 0.0, 9.0]))
    assert values == pytest.approx([-np.log(10.0), 0.0, np.log(10.0)])


def test_the_inner_validation_follows_the_inner_training_after_the_embargo(
    training: TrainingSet, settings: SelectionSettings
) -> None:
    """No candidate is ever measured on rows whose target the fit could have seen."""
    seen: list[tuple[pd.Timestamp, pd.Index]] = []

    def score(candidate: int, inner: TrainingSet, validation: pd.DataFrame) -> np.ndarray:
        seen.append((inner.grid["T0"].max(), validation.index))
        return np.full(len(validation), float(candidate))

    selection = select_candidate(
        training, [1, 2], settings, score, lambda candidate: {"candidate": candidate}
    )
    assert selection.fallback_reason == ""
    assert len(selection.scores) == 2
    inner_end, validation_index = seen[0]
    validation_start = training.grid.loc[validation_index, "T0"].min()
    assert inner_end + pd.Timedelta(days=settings.embargo_days) < validation_start


def test_ties_go_to_the_earlier_candidate(
    training: TrainingSet, settings: SelectionSettings
) -> None:
    """Two identical scores keep the first candidate, so runs agree."""
    selection = select_candidate(
        training,
        ["first", "second"],
        settings,
        lambda candidate, inner, validation: np.zeros(len(validation)),
        lambda candidate: {"candidate": candidate},
    )
    assert selection.params == "first"


def test_a_selection_without_two_classes_falls_back_loudly(
    training: TrainingSet, settings: SelectionSettings
) -> None:
    """Nothing to measure is said, not hidden behind a default."""
    negatives = training._replace(target=training.target * 0)
    selection = select_candidate(
        negatives,
        [0.1, 1.0],
        settings,
        lambda candidate, inner, validation: np.zeros(len(validation)),
        lambda candidate: {"regularisation": candidate},
    )
    assert selection.params == 0.1
    assert "single class" in selection.fallback_reason


def test_the_tuned_logistic_chooses_its_penalty_inside_every_fold(
    training: TrainingSet, settings: SelectionSettings, config: AppConfig
) -> None:
    """Same protocol as the trees: one selection per fold, on its training rows."""
    profile = config.sources.synthetic
    folds = temporal_folds(training.grid["T0"], 2, profile.horizon_days, profile.embargo_days)
    scorer = TunedLogisticScorer([0.1, 1.0], settings)
    result = evaluate_scorers(training, folds, [scorer], k=settings.k, frequency=settings.frequency)
    assert len(result.folds) == len(folds)
    assert len(scorer.selections) == len(folds)
    assert all(selection.params in (0.1, 1.0) for selection in scorer.selections)
    assert scorer.pipeline is not None
    assert list(scorer.pipeline.named_steps) == [
        "functiontransformer",
        "standardscaler",
        "logisticregression",
    ]


def test_the_tuned_logistic_scales_the_compressed_training_rows_only(
    training: TrainingSet, settings: SelectionSettings
) -> None:
    """Normalising on the test rows would leak, contract 3.3."""
    families = {FeatureSource.FINANCE, FeatureSource.GENERAL}
    scorer = TunedLogisticScorer([1.0], settings, families=families, name="logistic_tuned_finance")
    scorer.fit_score(training, training.features.head(5) * 1000, training.grid.head(5))
    assert scorer.pipeline is not None
    scoped = select_families(training.features, families)
    expected = signed_log1p(np.nan_to_num(scoped.to_numpy(dtype="float64"), posinf=0.0, neginf=0.0))
    scaler = scorer.pipeline.named_steps["standardscaler"]
    assert scaler.n_features_in_ == scoped.shape[1]
    assert scaler.mean_ == pytest.approx(expected.mean(axis=0))


def test_regularisation_strengths_must_be_positive(
    raw_config: dict[str, Any], write_yaml: Callable[[dict[str, Any]], Path]
) -> None:
    """A null penalty strength is refused at load time, never at fit time."""
    raw_config["evaluation"]["logistic_regularisation"] = [0.0, 1.0]
    with pytest.raises(ConfigError, match="logistic_regularisation"):
        load_config(write_yaml(raw_config))
