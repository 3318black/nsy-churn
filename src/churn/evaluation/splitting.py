"""Chronological folds with an embargo and a purge.

The target of a pair ``(client_id, T0)`` is known at ``T0 + horizon``, plus the
delay a termination needs to be confirmed. A plain chronological cut therefore
lets the last training rows carry an outcome that happens inside the test period:
the model learns from facts belonging to the window it is asked to predict.
Validation then looks excellent and production does not.

Two guards close that door, and both are applied rather than one assumed to
imply the other.

Embargo
    No training date may fall within ``embargo_days`` of the test start.
Purge
    No training row may have its target resolve at or after the test start.

**A target resolves when it is confirmed, not when it is dated.** On KKBox a
termination is dated at the expiry of the subscription, and confirmed only once
the 30 days allowed to renew have passed. A purge counted from the date alone
kept, on 2026-09-14, between 93 and 216 training positives per fold that were
confirmed after their test period had started. Decision D24.

**Why not scikit-learn's ``TimeSeriesSplit`` and its ``gap``.** The review of the
initial specification pointed to that parameter. It counts *samples*, not days,
and the grid holds a variable number of accounts per date: a gap of N rows would
cover a few days in a dense week and a month in a sparse one. The folds are
therefore cut on dates, which is what the embargo is expressed in.

The training window expands: each fold trains on everything that precedes its
embargo, as a model retrained on the full past would in production.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["TemporalFold", "count_resolution_overlaps", "temporal_folds"]


@dataclass(frozen=True, slots=True)
class TemporalFold:
    """One chronological fold.

    Attributes:
        index: position of the fold, starting at zero.
        train_index: positions of the training rows in the grid.
        test_index: positions of the test rows in the grid.
        test_start: first observation date of the test period.
        test_end: last observation date of the test period.
    """

    index: int
    train_index: np.ndarray
    test_index: np.ndarray
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def temporal_folds(
    observation_dates: pd.Series,
    n_splits: int,
    horizon_days: int,
    embargo_days: int,
    confirmation_delay_days: int = 0,
) -> list[TemporalFold]:
    """Cut the grid into chronological folds with an embargo and a purge.

    The distinct observation dates are split into ``n_splits + 1`` consecutive
    blocks. The first block only ever trains; each following block is the test
    period of one fold.

    Args:
        observation_dates: the ``T0`` column of the grid, one value per row.
        n_splits: number of folds.
        horizon_days: days the target resolves over.
        embargo_days: days kept empty between training and test.
        confirmation_delay_days: days after a termination date before the
            termination is a known fact.

    Returns:
        The folds, in chronological order. A fold left without any training row
        is skipped rather than returned empty.

    Raises:
        ValueError: when the embargo is shorter than the horizon plus the
            confirmation delay, or when the grid holds too few dates for the
            requested folds.
    """
    resolution_days = horizon_days + confirmation_delay_days
    if embargo_days < resolution_days:
        message = (
            f"embargo_days ({embargo_days}) is shorter than horizon_days ({horizon_days}) "
            f"plus confirmation_delay_days ({confirmation_delay_days}): training targets "
            f"would resolve inside the test period"
        )
        raise ValueError(message)

    dates = pd.DatetimeIndex(observation_dates.unique()).sort_values()
    if len(dates) < n_splits + 1:
        message = f"{len(dates)} observation dates cannot yield {n_splits} folds"
        raise ValueError(message)

    embargo = pd.Timedelta(days=embargo_days)
    resolved = observation_dates + pd.Timedelta(days=resolution_days)
    blocks = np.array_split(np.arange(len(dates)), n_splits + 1)

    folds: list[TemporalFold] = []
    for block in blocks[1:]:
        test_start = dates[block[0]]
        test_end = dates[block[-1]]
        in_test = observation_dates.between(test_start, test_end)
        before_embargo = observation_dates < test_start - embargo
        purged = resolved < test_start
        train_index = np.flatnonzero((before_embargo & purged).to_numpy())
        if train_index.size == 0:
            continue
        folds.append(
            TemporalFold(
                index=len(folds),
                train_index=train_index,
                test_index=np.flatnonzero(in_test.to_numpy()),
                test_start=test_start,
                test_end=test_end,
            )
        )
    return folds


def count_resolution_overlaps(
    fold: TemporalFold,
    observation_dates: pd.Series,
    horizon_days: int,
    confirmation_delay_days: int = 0,
) -> int:
    """Count the training rows whose target resolves at or after the test start.

    Any non zero value means the fold leaks the outcome of the test period into
    training. It is the property ``tests/test_split.py`` guards.

    Args:
        fold: the fold to check.
        observation_dates: the ``T0`` column of the grid.
        horizon_days: days the target resolves over.
        confirmation_delay_days: days after a termination date before the
            termination is a known fact.

    Returns:
        The number of leaking training rows.
    """
    resolution = pd.Timedelta(days=horizon_days + confirmation_delay_days)
    resolved = observation_dates.iloc[fold.train_index] + resolution
    return int((resolved >= fold.test_start).sum())
