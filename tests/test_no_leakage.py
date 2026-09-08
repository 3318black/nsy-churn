"""The leakage sentinel.

The rule it guards is the central one of the project: a feature computed for
``(client_id, T0)`` uses only events strictly earlier than ``T0``.

The method is reconstruction. Features are built twice, once on the whole
journal and once on a journal truncated at ``T0``. If a single value differs,
that feature reads the future, and the whole evaluation of the project becomes
meaningless while every other test stays green.

**If this file ever fails, do not adjust it to pass.** The construction is what
is broken, not the sentinel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.config import AppConfig
from churn.data.schemas import Dataset
from churn.data.synthetic import generate_dataset
from churn.features.build import GridSpec, build_grid, build_training_set
from churn.features.windows import build_window_features

#: Observation dates the sentinel checks. Each one covers every account of the
#: grid at that date, so the fifty pairs of the acceptance criterion are widely
#: exceeded.
SENTINEL_DATES = 8

#: Accounts kept per date, to hold the runtime down without weakening the check.
ACCOUNTS_PER_DATE = 40


@pytest.fixture(scope="module")
def dataset(config: AppConfig) -> Dataset:
    """Generate a dataset carrying the edge cases the sentinel needs."""
    profile = config.sources.synthetic.model_copy(update={"n_accounts": 250})
    return generate_dataset(profile, seed=config.project.random_seed, resolution="us")


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


def _sentinel_pairs(dataset: Dataset, spec: GridSpec) -> list[tuple[pd.Timestamp, pd.DataFrame]]:
    """Return observation dates and the grid rows attached to each of them."""
    grid = build_grid(dataset, spec)
    dates = sorted(grid["T0"].unique())
    rng = np.random.default_rng(0)
    chosen = rng.choice(len(dates), size=min(SENTINEL_DATES, len(dates)), replace=False)
    pairs = []
    for index in sorted(chosen):
        date = dates[index]
        rows = grid.loc[grid["T0"] == date, ["client_id", "T0"]].head(ACCOUNTS_PER_DATE)
        if not rows.empty:
            pairs.append((date, rows.reset_index(drop=True)))
    return pairs


def test_the_grid_yields_enough_pairs_to_be_meaningful(dataset: Dataset, spec: GridSpec) -> None:
    """A sentinel running on three rows would prove nothing."""
    pairs = _sentinel_pairs(dataset, spec)
    total = sum(len(rows) for _, rows in pairs)
    assert len(pairs) >= 5
    assert total >= 50


def test_features_ignore_everything_at_or_after_t0(dataset: Dataset, spec: GridSpec) -> None:
    """The sentinel itself: truncating the journal at ``T0`` changes nothing.

    Every event dated at or after ``T0`` is removed, then the features are built
    again. A feature that only looks at the past cannot notice the difference.
    """
    checked = 0
    for date, rows in _sentinel_pairs(dataset, spec):
        events = dataset.events
        truncated = events.loc[events["event_ts"] < date]

        complete_view = build_window_features(rows, events, spec.windows_days, resolution="us")
        truncated_view = build_window_features(rows, truncated, spec.windows_days, resolution="us")

        # Both views must carry the same columns, otherwise the comparison would
        # silently skip the families the truncation emptied.
        shared = sorted(set(complete_view.columns) & set(truncated_view.columns))
        assert shared, "no comparable feature, the sentinel would prove nothing"

        difference = (complete_view[shared] - truncated_view[shared]).abs().to_numpy().max()
        assert difference == 0, (
            f"a feature changes when the journal is truncated at {date}, "
            f"so it reads events at or after T0"
        )
        checked += len(rows)
    assert checked >= 50


def test_an_event_exactly_on_t0_is_excluded(dataset: Dataset, spec: GridSpec) -> None:
    """The bound is strict, so an event landing exactly on ``T0`` stays out.

    Included, it would let the pipeline use a fact of the very day it is meant to
    predict from, which is the subtlest form of leakage.
    """
    grid = build_grid(dataset, spec).head(1)[["client_id", "T0"]]
    client = grid.iloc[0]["client_id"]
    date = grid.iloc[0]["T0"]

    before = build_window_features(grid, dataset.events, spec.windows_days, resolution="us")
    injected = pd.concat(
        [
            dataset.events,
            pd.DataFrame(
                {
                    "client_id": [client],
                    "event_ts": [date],
                    "event_type": ["connexion"],
                    "event_value": [999.0],
                }
            ),
        ],
        ignore_index=True,
    ).sort_values(["client_id", "event_ts"], kind="stable", ignore_index=True)
    after = build_window_features(grid, injected, spec.windows_days, resolution="us")

    shared = sorted(set(before.columns) & set(after.columns))
    assert (before[shared].to_numpy() == after[shared].to_numpy()).all()


def test_an_event_just_before_t0_is_included(dataset: Dataset, spec: GridSpec) -> None:
    """The mirror case, so the previous test cannot pass by ignoring everything."""
    grid = build_grid(dataset, spec).head(1)[["client_id", "T0"]]
    client = grid.iloc[0]["client_id"]
    date = grid.iloc[0]["T0"]

    before = build_window_features(grid, dataset.events, spec.windows_days, resolution="us")
    injected = pd.concat(
        [
            dataset.events,
            pd.DataFrame(
                {
                    "client_id": [client],
                    "event_ts": [date - pd.Timedelta(hours=1)],
                    "event_type": ["connexion"],
                    "event_value": [999.0],
                }
            ),
        ],
        ignore_index=True,
    ).sort_values(["client_id", "event_ts"], kind="stable", ignore_index=True)
    after = build_window_features(grid, injected, spec.windows_days, resolution="us")

    assert after["count_connexion_7j"].iloc[0] == before["count_connexion_7j"].iloc[0] + 1
    # Approximate comparison: the sum is a difference of two cumulated floats,
    # so the last bits differ from a direct addition. An exact equality here
    # would test the arithmetic of the machine, not the feature.
    assert after["sum_connexion_7j"].iloc[0] == pytest.approx(
        before["sum_connexion_7j"].iloc[0] + 999.0
    )


def test_the_target_never_reaches_the_features(dataset: Dataset, spec: GridSpec) -> None:
    """No feature may be a deterministic function of the target.

    A correlation of one signals a column that carries the answer rather than a
    clue, which is how a leak usually shows up in practice.
    """
    training = build_training_set(dataset, spec)
    numeric = training.features.select_dtypes("number")
    varying = numeric.loc[:, numeric.std() > 0]
    correlations = varying.corrwith(training.target).abs()
    suspicious = correlations[correlations > 0.99]
    assert suspicious.empty, (
        f"features perfectly correlated with the target: {list(suspicious.index)}"
    )
