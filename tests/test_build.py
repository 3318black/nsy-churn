"""Tests of the observation grid and of the target."""

from __future__ import annotations

import pandas as pd
import pytest

from churn.config import AppConfig
from churn.data.schemas import Dataset
from churn.data.synthetic import generate_dataset
from churn.features.build import GridSpec, build_grid, build_training_set


@pytest.fixture(scope="module")
def spec(config: AppConfig) -> GridSpec:
    """Return the grid specification of the synthetic profile."""
    return GridSpec(
        horizon_days=config.sources.synthetic.horizon_days,
        min_account_age_days=config.business.min_account_age_days,
        min_history_days=config.features.min_history_days,
        observation_frequency=config.features.observation_frequency,
        windows_days=tuple(config.features.windows_days),
        resolution="us",
    )


@pytest.fixture(scope="module")
def dataset(config: AppConfig) -> Dataset:
    """Generate a dataset large enough to carry positives."""
    profile = config.sources.synthetic.model_copy(update={"n_accounts": 250})
    return generate_dataset(profile, seed=config.project.random_seed, resolution="us")


def _dataset_of(accounts: pd.DataFrame, events: pd.DataFrame) -> Dataset:
    """Return a dataset from two hand written frames."""
    return Dataset(accounts=accounts, events=events)


def _one_account(started: str, ended: str | None = None) -> pd.DataFrame:
    """Return a single account reference row."""
    return pd.DataFrame(
        {
            "client_id": ["A"],
            "date_debut_contrat": pd.to_datetime([started], utc=True).as_unit("us"),
            "date_resiliation": pd.to_datetime([ended], utc=True).as_unit("us"),
            "type_contrat": ["mensuel"],
            "mrr": [100.0],
            "segment": ["PME"],
            "canal_acquisition": ["direct"],
            "nb_licences": [3],
        }
    )


def _events_between(start: str, end: str) -> pd.DataFrame:
    """Return one connection event per week between two dates."""
    stamps = pd.date_range(start, end, freq="W-WED", tz="UTC").as_unit("us")
    return pd.DataFrame(
        {
            "client_id": ["A"] * len(stamps),
            "event_ts": stamps,
            "event_type": ["connexion"] * len(stamps),
            "event_value": [1.0] * len(stamps),
        }
    )


def test_the_grid_carries_the_expected_columns(dataset: Dataset, spec: GridSpec) -> None:
    """The grid holds the identity, the date, the target and what evaluation needs."""
    grid = build_grid(dataset, spec)
    assert list(grid.columns) == ["client_id", "T0", "y", "mrr"]
    assert grid["y"].isin([0, 1]).all()


def test_the_grid_is_deterministically_ordered(dataset: Dataset, spec: GridSpec) -> None:
    """Two runs on the same data yield the very same frame."""
    first = build_grid(dataset, spec)
    second = build_grid(dataset, spec)
    assert first.equals(second)
    assert first["T0"].is_monotonic_increasing


def test_young_accounts_are_absent(dataset: Dataset, spec: GridSpec) -> None:
    """Criterion 5 of lot 3: an account too young carries no usable history."""
    grid = build_grid(dataset, spec)
    started = (
        dataset.accounts.set_index("client_id")["date_debut_contrat"]
        .reindex(grid["client_id"])
        .to_numpy(dtype="datetime64[us]")
    )
    ages = grid["T0"].dt.tz_localize(None).to_numpy() - started
    assert (ages >= pd.Timedelta(days=spec.min_account_age_days).to_timedelta64()).all()


def test_terminated_accounts_leave_the_grid_after_their_termination(
    dataset: Dataset, spec: GridSpec
) -> None:
    """Scoring an account that has already left would be meaningless."""
    grid = build_grid(dataset, spec)
    ended = (
        dataset.accounts.set_index("client_id")["date_resiliation"]
        .reindex(grid["client_id"])
        .to_numpy(dtype="datetime64[us]")
    )
    terminated = ~pd.isna(ended)
    observed = grid["T0"].dt.tz_localize(None).to_numpy()
    assert (observed[terminated] < ended[terminated]).all()


def test_a_pair_with_an_unknown_outcome_is_dropped_not_labelled_zero(spec: GridSpec) -> None:
    """Criterion 4 of lot 3, and the subtlest bias of the whole build.

    Labelling such a pair zero would claim the account survived, when the truth
    is that nobody knows yet. The bias would land entirely on the most recent
    period, which is exactly the one a model is judged on.
    """
    accounts = _one_account("2025-01-01")
    events = _events_between("2025-01-01", "2025-12-31")
    grid = build_grid(_dataset_of(accounts, events), spec)

    history_end = events["event_ts"].max()
    horizon = pd.Timedelta(days=spec.horizon_days)
    assert not grid.empty
    assert (grid["T0"] + horizon <= history_end).all()


def test_the_target_marks_a_termination_inside_the_horizon(spec: GridSpec) -> None:
    """A termination inside the window is a positive, outside it is not."""
    accounts = _one_account("2025-01-01", "2025-09-15")
    events = _events_between("2025-01-01", "2025-12-31")
    grid = build_grid(_dataset_of(accounts, events), spec).set_index("T0")

    termination = pd.Timestamp("2025-09-15", tz="UTC")
    horizon = pd.Timedelta(days=spec.horizon_days)
    for date, row in grid.iterrows():
        inside = termination > date and termination <= date + horizon
        assert bool(row["y"]) is inside, f"target wrong at {date}"


def test_an_account_never_terminating_has_only_negatives(spec: GridSpec) -> None:
    """The mirror case, so the target cannot be positive by construction."""
    accounts = _one_account("2025-01-01")
    events = _events_between("2025-01-01", "2025-12-31")
    grid = build_grid(_dataset_of(accounts, events), spec)
    assert (grid["y"] == 0).all()


def test_an_empty_dataset_yields_an_empty_grid(spec: GridSpec) -> None:
    """The empty path needs no special casing downstream."""
    accounts = _one_account("2025-01-01").head(0)
    events = _events_between("2025-01-01", "2025-01-02").head(0)
    assert build_grid(_dataset_of(accounts, events), spec).empty


def test_the_training_set_is_aligned_row_by_row(dataset: Dataset, spec: GridSpec) -> None:
    """The three pieces must line up, or every later metric is meaningless."""
    training = build_training_set(dataset, spec)
    assert len(training.grid) == len(training.target) == len(training.features)
    assert training.grid.index.equals(training.features.index)


def test_the_feature_matrix_holds_no_missing_value(dataset: Dataset, spec: GridSpec) -> None:
    """An absence of event is a zero, a known and precise fact."""
    training = build_training_set(dataset, spec)
    assert not training.features.isna().to_numpy().any()


def test_structural_features_are_known_at_t0(dataset: Dataset, spec: GridSpec) -> None:
    """Account age is a difference against ``T0`` itself, so it carries no future."""
    training = build_training_set(dataset, spec)
    assert (training.features["anciennete_jours"] >= spec.min_account_age_days).all()
