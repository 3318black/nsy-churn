"""Tests of the chronological folds, decision D4.

The central one fails as soon as a training row carries a target that resolves
at or after the start of its test period. That is the leak a plain chronological
cut lets through, and the reason the embargo exists.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

from churn.evaluation.splitting import (
    TemporalFold,
    count_resolution_overlaps,
    temporal_folds,
)

HORIZON = 30


def _weekly_dates(weeks: int = 60, accounts_per_week: int = 5) -> pd.Series:
    """Return a grid ``T0`` column, several accounts per weekly date."""
    dates = pd.date_range("2024-01-01", periods=weeks, freq="W-MON", tz="UTC").as_unit("us")
    return pd.Series(np.repeat(dates, accounts_per_week))


def test_no_training_target_resolves_inside_the_test_period() -> None:
    """Criterion 1 of lot 4, checked on every fold."""
    dates = _weekly_dates()
    folds = temporal_folds(dates, n_splits=4, horizon_days=HORIZON, embargo_days=HORIZON)
    assert folds
    for fold in folds:
        assert count_resolution_overlaps(fold, dates, HORIZON) == 0


def test_the_overlap_check_catches_a_leaking_fold() -> None:
    """The guard must be able to fail, or it proves nothing.

    A fold built by hand without any embargo trains on the weeks right before
    the test start, whose targets resolve inside the test period.
    """
    dates = _weekly_dates()
    test_start = dates.unique()[40]
    leaking = TemporalFold(
        index=0,
        train_index=np.flatnonzero((dates < test_start).to_numpy()),
        test_index=np.flatnonzero((dates >= test_start).to_numpy()),
        test_start=test_start,
        test_end=dates.max(),
    )
    assert count_resolution_overlaps(leaking, dates, HORIZON) > 0


def test_an_embargo_shorter_than_the_horizon_is_refused() -> None:
    """Refused at the source, rather than trusted to a later check."""
    with pytest.raises(ValueError, match="shorter than horizon_days"):
        temporal_folds(_weekly_dates(), n_splits=3, horizon_days=60, embargo_days=30)


def test_too_few_dates_for_the_requested_folds_is_refused() -> None:
    """A fold count the grid cannot honour is an error, never a silent shortfall."""
    with pytest.raises(ValueError, match="cannot yield"):
        temporal_folds(_weekly_dates(weeks=3), n_splits=5, horizon_days=7, embargo_days=7)


def test_training_always_precedes_the_embargo() -> None:
    """Every training date sits at least one embargo before the test start."""
    dates = _weekly_dates()
    embargo = 45
    for fold in temporal_folds(dates, n_splits=4, horizon_days=HORIZON, embargo_days=embargo):
        latest_train = dates.iloc[fold.train_index].max()
        assert latest_train < fold.test_start - pd.Timedelta(days=embargo)


def test_test_periods_are_consecutive_and_disjoint() -> None:
    """No row is tested twice, and the folds move forward in time."""
    dates = _weekly_dates()
    folds = temporal_folds(dates, n_splits=4, horizon_days=HORIZON, embargo_days=HORIZON)
    seen: set[int] = set()
    for previous, current in pairwise(folds):
        assert previous.test_end < current.test_start
    for fold in folds:
        assert seen.isdisjoint(fold.test_index.tolist())
        seen.update(fold.test_index.tolist())


def test_the_training_window_expands() -> None:
    """Each fold trains on the whole past before its embargo."""
    dates = _weekly_dates()
    folds = temporal_folds(dates, n_splits=4, horizon_days=HORIZON, embargo_days=HORIZON)
    sizes = [len(fold.train_index) for fold in folds]
    assert sizes == sorted(sizes)
    assert sizes[0] < sizes[-1]


def test_every_row_of_a_test_date_is_in_the_test_set() -> None:
    """A fold cut on dates keeps all the accounts of a date together."""
    dates = _weekly_dates(accounts_per_week=7)
    for fold in temporal_folds(dates, n_splits=3, horizon_days=HORIZON, embargo_days=HORIZON):
        tested = dates.iloc[fold.test_index]
        assert (tested.value_counts() == 7).all()
