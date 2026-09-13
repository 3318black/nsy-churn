"""Tests of the baselines, of the protocol and of the report."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from churn.config import AppConfig, FeatureSource
from churn.data.synthetic import generate_dataset
from churn.evaluation.baselines import (
    LogisticScorer,
    RandomScorer,
    RevenueScorer,
    default_baselines,
)
from churn.evaluation.protocol import evaluate_scorers, summarise
from churn.evaluation.report import source_banner, write_evaluation_report
from churn.evaluation.splitting import temporal_folds
from churn.features.build import GridSpec, TrainingSet, build_training_set
from churn.features.catalog import select_families


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


def _toy() -> tuple[TrainingSet, pd.DataFrame, pd.DataFrame]:
    """Return a tiny separable problem: training rows, test features, test grid."""
    rng = np.random.default_rng(1)
    features = pd.DataFrame({"a": rng.normal(size=200), "b": rng.normal(10.0, 5.0, size=200)})
    train = TrainingSet(
        grid=pd.DataFrame({"mrr": np.linspace(1.0, 50.0, 200)}),
        target=pd.Series((features["a"] > 0).astype(int)),
        features=features,
    )
    test = pd.DataFrame({"a": [-2.0, 2.0], "b": [10.0, 10.0]})
    grid = pd.DataFrame({"mrr": [5.0, 9.0]})
    return train, test, grid


def test_random_scores_are_reproducible() -> None:
    """Same seed, same ranking."""
    train, test, grid = _toy()
    first = RandomScorer(7).fit_score(train, test, grid)
    second = RandomScorer(7).fit_score(train, test, grid)
    assert np.array_equal(first, second)


def test_revenue_scores_are_the_revenue() -> None:
    """The tool less salesperson calls the biggest accounts first."""
    train, test, grid = _toy()
    assert list(RevenueScorer().fit_score(train, test, grid)) == [5.0, 9.0]


def test_logistic_learns_a_separable_signal() -> None:
    """Sanity check that the baseline is a real model."""
    train, test, grid = _toy()
    scores = LogisticScorer().fit_score(train, test, grid)
    assert scores[1] > scores[0]


def test_the_scaler_is_fitted_on_training_rows_only() -> None:
    """Normalising on the whole grid before splitting is a leak, contract 3.3."""
    train, test, grid = _toy()
    scorer = LogisticScorer()
    scorer.fit_score(train, test.assign(b=1_000.0), grid)
    assert scorer.pipeline is not None
    scaler = scorer.pipeline.named_steps["standardscaler"]
    assert scaler.mean_[1] == pytest.approx(train.features["b"].mean())


def test_infinite_features_do_not_break_the_solver() -> None:
    """A trend over a zero denominator must not crash the baseline."""
    train, test, grid = _toy()
    train.features.loc[0, "b"] = np.inf
    scores = LogisticScorer().fit_score(train, test, grid)
    assert np.isfinite(scores).all()


def test_a_single_class_fold_yields_constant_scores() -> None:
    """Nothing to learn is reported, not crashed on."""
    train, test, grid = _toy()
    negatives = train._replace(target=pd.Series([0] * len(train.target)))
    scores = LogisticScorer().fit_score(negatives, test, grid)
    assert (scores == 0).all()


def test_a_logistic_restricted_to_finance_never_sees_the_other_families(
    training: TrainingSet,
) -> None:
    """The ablation of lot 5 compares families, so the restriction must hold."""
    families = {FeatureSource.FINANCE, FeatureSource.GENERAL}
    scorer = LogisticScorer(families=families, name="logistic_finance")
    head = training.grid.head(5).drop(columns="y")
    scorer.fit_score(training, training.features.head(5), head)
    assert scorer.name == "logistic_finance"
    assert scorer.pipeline is not None
    expected = select_families(training.features, families).shape[1]
    assert scorer.pipeline.n_features_in_ == expected < training.features.shape[1]


def test_the_protocol_evaluates_every_scorer_on_every_fold(
    training: TrainingSet, config: AppConfig
) -> None:
    """Criterion 3 of lot 4: the three baselines go through the same folds."""
    profile = config.sources.synthetic
    folds = temporal_folds(
        training.grid["T0"],
        n_splits=3,
        horizon_days=profile.horizon_days,
        embargo_days=profile.embargo_days,
    )
    result = evaluate_scorers(
        training,
        folds,
        default_baselines(seed=1),
        k=config.business.weekly_capacity_k,
        frequency=config.evaluation.scoring_period,
    )
    assert len(result.folds) == len(folds) * 3
    assert set(result.folds["scorer"]) == {"random", "revenue", "logistic"}

    summary = summarise(result)
    assert "lift_vs_revenue" in summary.columns
    assert summary.set_index("scorer").loc["revenue", "lift_vs_revenue"] == pytest.approx(1.0)


class _SpyScorer:
    """Records what the protocol hands to a scorer."""

    name = "spy"

    def __init__(self) -> None:
        self.test_grid_columns: set[str] = set()

    def fit_score(
        self, train: TrainingSet, test_features: pd.DataFrame, test_grid: pd.DataFrame
    ) -> np.ndarray:
        del train
        self.test_grid_columns |= set(test_grid.columns)
        return np.zeros(len(test_features))


def test_the_test_target_never_reaches_a_scorer(training: TrainingSet, config: AppConfig) -> None:
    """A scorer handed the test grid with its target could read the answer."""
    profile = config.sources.synthetic
    folds = temporal_folds(training.grid["T0"], 2, profile.horizon_days, profile.embargo_days)
    spy = _SpyScorer()
    evaluate_scorers(training, folds, [spy], k=10, frequency="W-MON")
    assert spy.test_grid_columns
    assert "y" not in spy.test_grid_columns


def test_every_report_states_its_source(
    training: TrainingSet, config: AppConfig, tmp_path: Path
) -> None:
    """Criterion 4 of lot 4, decision D2: the source opens every artefact."""
    profile = config.sources.synthetic
    folds = temporal_folds(training.grid["T0"], 2, profile.horizon_days, profile.embargo_days)
    result = evaluate_scorers(training, folds, default_baselines(seed=1), k=20, frequency="W-MON")

    synthetic_dir = tmp_path / "synthetic"
    written = write_evaluation_report(result, synthetic_dir, profile.label, True, "W-MON")
    for path in written:
        if path.suffix in {".md", ".csv"}:
            assert "SIMULATED DATA" in path.read_text(encoding="utf-8").splitlines()[0]

    real_dir = tmp_path / "real"
    real = write_evaluation_report(result, real_dir, "KKBox", False, "W-MON")
    summary = next(path for path in real if path.suffix == ".md")
    assert summary.read_text(encoding="utf-8").startswith("> Source: KKBox")


def test_the_banner_never_hides_a_synthetic_source() -> None:
    """The simulated statement is not optional wording."""
    assert "No performance figure holds here" in source_banner("x", is_synthetic=True)
    assert "SIMULATED" not in source_banner("x", is_synthetic=False)


def test_a_fold_without_positive_training_rows_is_refused(
    training: TrainingSet, config: AppConfig
) -> None:
    """Measured on KKBox before decision D17: every fold trained on zero
    positives, and the logistic baseline silently matched the revenue ranking.
    Such a fold must fail loudly rather than yield a number."""
    profile = config.sources.synthetic
    folds = temporal_folds(training.grid["T0"], 2, profile.horizon_days, profile.embargo_days)
    negatives = training._replace(target=training.target * 0)
    with pytest.raises(ValueError, match="single"):
        evaluate_scorers(negatives, folds, default_baselines(seed=1), k=10, frequency="W-MON")
