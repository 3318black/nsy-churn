"""The brute force check.

Complementary to the sentinel and of a different nature. The sentinel proves the
features do not read the future; this file proves the arithmetic is right.

Each window feature is recomputed by naive filtering, walking the events of one
account and counting those inside the interval. The vectorised result must match
exactly.

**This is the only check that would have caught the 10.5% of wrong rows measured
on 2026-09-07.** No assertion on totals, means or frame shapes spots them: the
figures stay plausible, the frame stays the right size, and one row in ten is
simply false. It stays required whatever library is used underneath.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from churn.config import AppConfig
from churn.data.schemas import Dataset
from churn.data.synthetic import generate_dataset
from churn.features.build import GridSpec, build_grid
from churn.features.windows import build_window_features

#: Pairs checked against the naive computation. The acceptance criterion of lot 3
#: sets the floor at two hundred.
BRUTE_FORCE_PAIRS = 250


@pytest.fixture(scope="module")
def dataset(config: AppConfig) -> Dataset:
    """Generate a dataset holding duplicated timestamps and missing values."""
    profile = config.sources.synthetic.model_copy(update={"n_accounts": 200})
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


def _naive_window(
    events: pd.DataFrame,
    client_id: str,
    upper: pd.Timestamp,
    window_days: int,
    event_type: str,
) -> tuple[int, float]:
    """Count and sum the events of one window, by plain filtering.

    The bounds mirror the contract: ``[T0 - window, T0[``, upper bound excluded.
    """
    lower = upper - pd.Timedelta(days=window_days)
    of_client = events.loc[
        (events["client_id"] == client_id) & (events["event_type"] == event_type)
    ]
    inside = of_client.loc[(of_client["event_ts"] >= lower) & (of_client["event_ts"] < upper)]
    return len(inside), float(inside["event_value"].fillna(0.0).sum())


def test_the_generated_journal_carries_duplicated_timestamps(dataset: Dataset) -> None:
    """Without them the check below would exercise the easy case only."""
    duplicated = dataset.events.duplicated(["client_id", "event_ts"], keep=False)
    assert duplicated.mean() > 0.05


def test_window_counts_match_a_naive_computation(dataset: Dataset, spec: GridSpec) -> None:
    """The check itself, on counts and on sums, over every window and family."""
    grid = build_grid(dataset, spec)
    rng = np.random.default_rng(20260908)
    sample = grid.iloc[rng.choice(len(grid), size=min(BRUTE_FORCE_PAIRS, len(grid)), replace=False)]
    sample = sample[["client_id", "T0"]].reset_index(drop=True)
    assert len(sample) >= 200, "sample below the acceptance floor of lot 3"

    features = build_window_features(sample, dataset.events, spec.windows_days, resolution="us")
    event_types = sorted(set(dataset.events["event_type"]))

    mismatches: list[str] = []
    for position in range(len(sample)):
        client_id = sample.iloc[position]["client_id"]
        upper = sample.iloc[position]["T0"]
        for window in spec.windows_days:
            for event_type in event_types:
                count_column = f"count_{event_type}_{window}j"
                sum_column = f"sum_{event_type}_{window}j"
                if count_column not in features.columns:
                    continue
                expected_count, expected_sum = _naive_window(
                    dataset.events, client_id, upper, window, event_type
                )
                actual_count = features.iloc[position][count_column]
                actual_sum = features.iloc[position][sum_column]
                if actual_count != expected_count:
                    mismatches.append(
                        f"{client_id} at {upper} on {count_column}: "
                        f"{actual_count} instead of {expected_count}"
                    )
                if abs(actual_sum - expected_sum) > 1e-6:
                    mismatches.append(
                        f"{client_id} at {upper} on {sum_column}: "
                        f"{actual_sum} instead of {expected_sum}"
                    )

    assert not mismatches, "\n".join(mismatches[:10])


def test_a_window_without_event_yields_zero(dataset: Dataset, spec: GridSpec) -> None:
    """An absence is a zero, never a missing value.

    A missing value here would propagate into the model as an unknown, when the
    fact is known and precise: nothing happened.
    """
    grid = build_grid(dataset, spec).head(200)[["client_id", "T0"]]
    features = build_window_features(grid, dataset.events, spec.windows_days, resolution="us")
    assert not features.isna().to_numpy().any()
    counts = features[[name for name in features.columns if name.startswith("count_")]]
    assert (counts.to_numpy() >= 0).all()


def test_a_client_without_any_event_yields_zeros(dataset: Dataset, spec: GridSpec) -> None:
    """An account absent from the journal is not a crash and not a hole."""
    grid = pd.DataFrame(
        {
            "client_id": ["INCONNU"],
            "T0": [dataset.events["event_ts"].max()],
        }
    )
    features = build_window_features(grid, dataset.events, spec.windows_days, resolution="us")
    # Only the raw counts, not the trends: a trend over two empty windows is a
    # neutral ratio of one, which is the intended value and not a leak.
    counts = features[[name for name in features.columns if name.startswith("count_")]]
    assert (counts.to_numpy() == 0).all()
    trends = features[[name for name in features.columns if name.startswith("trend_")]]
    assert (trends.to_numpy() == 1.0).all()


def test_an_empty_grid_yields_an_empty_frame(dataset: Dataset, spec: GridSpec) -> None:
    """The empty path needs no special casing downstream."""
    empty = pd.DataFrame(
        {"client_id": pd.Series(dtype="str"), "T0": pd.Series(dtype="datetime64[us, UTC]")}
    )
    features = build_window_features(empty, dataset.events, spec.windows_days, resolution="us")
    assert features.empty
