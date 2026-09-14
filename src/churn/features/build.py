"""Construction of the training grid, the target and the feature matrix.

The grid is a set of ``(client_id, T0)`` pairs. Each pair asks one question: on
that date, was this account about to terminate within the horizon?

Three rules decide what enters the grid, and each exists to keep the answer
honest.

Eligibility
    The account is active at ``T0``, old enough to carry a usable history, and
    the journal covers the longest window a feature needs. An account observed
    for a week produces features that are structurally empty.
Target
    ``y = 1`` when the termination falls in ``]T0, T0 + horizon]``.
Unknown outcome
    A pair whose target window runs past the end of the history is **dropped**,
    never labelled zero. Labelling it zero would state that the account survived,
    when the truth is that nobody knows yet. The bias would land entirely on the
    most recent period, precisely the one a model is judged on.

The central rule of the module, and of the project: a feature computed for
``(client_id, T0)`` uses only events strictly earlier than ``T0``, and no column
of the reference table that postdates it. The sentinel of
``tests/test_no_leakage.py`` checks it by reconstruction.

**The revenue of a pair is read from the journal, never from the reference.**
The reference describes each account at extraction time. On KKBox its revenue
comes from the last transaction, and on 2026-09-13 it differed from the revenue
in force at ``T0`` on 22.5% of the grid rows and on 32.6% of the positive ones.
The sentinel could not see it, since it truncates the journal and not the
reference. Decision D18.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import pandas as pd

from churn.data.schemas import Dataset, DatetimeResolution, EventType
from churn.features.windows import build_window_features, read_state_at

__all__ = [
    "GridSpec",
    "ScoringSet",
    "TrainingSet",
    "build_grid",
    "build_scoring_set",
    "build_training_set",
    "observation_dates",
]


@dataclass(frozen=True, slots=True)
class GridSpec:
    """Shape of the observation grid.

    Attributes:
        horizon_days: days the target is resolved over.
        min_account_age_days: age an account must reach to enter the grid.
        min_history_days: history depth the longest window needs.
        observation_frequency: pandas frequency of the ``T0`` dates.
        windows_days: window lengths the features are built on.
        resolution: timestamp resolution.
    """

    horizon_days: int
    min_account_age_days: int
    min_history_days: int
    observation_frequency: str
    windows_days: tuple[int, ...]
    resolution: DatetimeResolution = "us"


class TrainingSet(NamedTuple):
    """The grid, its target and its feature matrix, aligned row by row.

    Attributes:
        grid: ``client_id``, ``T0`` and the columns carried for evaluation.
        target: the binary target.
        features: the feature matrix.
    """

    grid: pd.DataFrame
    target: pd.Series
    features: pd.DataFrame


def observation_dates(events: pd.DataFrame, spec: GridSpec) -> pd.DatetimeIndex:
    """Return the observation dates covering the usable history.

    The history starts where the journal starts, never at the oldest account
    registration. On KKBox, registrations go back to 2004 while transactions only
    begin in January 2015: starting from the registrations produced ten years of
    weekly dates where no termination could ever be observed, 56% of the grid,
    and training folds holding not a single positive. See decision D17.
    """
    if events.empty:
        return pd.DatetimeIndex([], dtype=f"datetime64[{spec.resolution}, UTC]")
    first = events["event_ts"].min()
    last = events["event_ts"].max()
    start = first + pd.Timedelta(days=spec.min_history_days)
    return pd.date_range(start, last, freq=spec.observation_frequency, tz="UTC").as_unit(
        spec.resolution
    )


class ScoringSet(NamedTuple):
    """The accounts to score on one date, and their features.

    Attributes:
        grid: ``client_id``, ``T0`` and ``mrr``, the revenue in force at ``T0``.
        features: the feature matrix, aligned row by row on ``grid``.
        date: the scoring date, kept even when no account is eligible.
    """

    grid: pd.DataFrame
    features: pd.DataFrame
    date: pd.Timestamp


def _eligible_pairs(dataset: Dataset, spec: GridSpec, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Return the ``(client_id, T0)`` pairs an account may be observed on.

    These rules are shared by training and scoring, so a model is never asked
    about an account it could not have learned from. The rule on a known outcome
    is not here: it belongs to training alone, since scoring is precisely about an
    outcome nobody knows yet.
    """
    accounts = dataset.accounts
    minimum_age = pd.Timedelta(days=spec.min_account_age_days)
    grid = pd.MultiIndex.from_product(
        [accounts["client_id"].to_numpy(), dates], names=["client_id", "T0"]
    ).to_frame(index=False)
    grid = grid.join(
        accounts.set_index("client_id")[["date_debut_contrat", "date_resiliation"]],
        on="client_id",
    )

    ended = grid["date_resiliation"]
    active = ended.isna() | (ended > grid["T0"])
    old_enough = (grid["T0"] - grid["date_debut_contrat"]) >= minimum_age

    # An account enters the grid only once it has been observed, with at least
    # one event strictly before T0. Before that it is registered but not yet a
    # customer, and predicting its termination means nothing. The first event is
    # read strictly before T0, so eligibility depends on no later fact.
    first_seen = dataset.events.groupby("client_id")["event_ts"].min().rename("first_seen")
    grid = grid.join(first_seen, on="client_id")
    observed = grid["first_seen"].notna() & (grid["first_seen"] < grid["T0"])

    return grid.loc[active & old_enough & observed].copy()


def _revenue_at_t0(grid: pd.DataFrame, dataset: Dataset, spec: GridSpec) -> pd.Series:
    """Return the revenue in force strictly before ``T0``, zero when none is known.

    Zero means unknown rather than free: the KKBox extract starts in 2015, and a
    long plan bought earlier only shows at its renewal. It is never filled from
    the reference, which would bring the leak of decision D18 back.
    """
    return read_state_at(
        grid, dataset.events, EventType.REVENU_MENSUEL.value, spec.resolution
    ).fillna(0.0)


def build_grid(dataset: Dataset, spec: GridSpec) -> pd.DataFrame:
    """Build the observation grid and its target.

    Args:
        dataset: the two contract tables.
        spec: shape of the grid.

    Returns:
        A frame with ``client_id``, ``T0``, ``y`` and the columns carried for
        evaluation, sorted deterministically.
    """
    dates = observation_dates(dataset.events, spec)
    if dataset.accounts.empty or len(dates) == 0:
        return pd.DataFrame(columns=["client_id", "T0", "y", "mrr"])

    history_end = dataset.events["event_ts"].max()
    horizon = pd.Timedelta(days=spec.horizon_days)
    grid = _eligible_pairs(dataset, spec, dates)

    # A pair whose target window runs past the end of the history has an unknown
    # outcome, not a negative one. Labelling it zero would bias the most recent
    # period, which is exactly the one a model is judged on.
    grid = grid.loc[(grid["T0"] + horizon) <= history_end].copy()
    ended = grid["date_resiliation"]
    grid["y"] = (ended.notna() & (ended > grid["T0"]) & (ended <= grid["T0"] + horizon)).astype(
        "int64"
    )
    grid["mrr"] = _revenue_at_t0(grid, dataset, spec)

    return grid.loc[:, ["client_id", "T0", "y", "mrr"]].sort_values(
        ["T0", "client_id"], kind="stable", ignore_index=True
    )


def build_scoring_set(
    dataset: Dataset, spec: GridSpec, scoring_date: pd.Timestamp | None = None
) -> ScoringSet:
    """Build the accounts to score on one date, and their features.

    The same eligibility rules and the same features as training apply, so the
    model sees on Monday exactly what it learned from. Only the target is absent:
    on the scoring date, nobody knows the outcome yet.

    Args:
        dataset: the two contract tables.
        spec: shape of the grid.
        scoring_date: timezone aware scoring date. Defaults to the last
            observation date the journal allows.

    Returns:
        The eligible accounts, sorted by identifier, and their features.

    Raises:
        ValueError: when the scoring date carries no timezone, or when the
            journal allows no observation date at all.
    """
    if scoring_date is None:
        dates = observation_dates(dataset.events, spec)
        if len(dates) == 0:
            message = "the journal is too short to allow any observation date"
            raise ValueError(message)
        date = dates[-1]
    else:
        if scoring_date.tzinfo is None:
            message = f"the scoring date {scoring_date} must carry a timezone"
            raise ValueError(message)
        date = scoring_date.tz_convert("UTC").as_unit(spec.resolution)

    grid = _eligible_pairs(dataset, spec, pd.DatetimeIndex([date]))
    if grid.empty:
        empty = pd.DataFrame(columns=["client_id", "T0", "mrr"])
        return ScoringSet(grid=empty, features=pd.DataFrame(index=empty.index), date=date)
    grid["mrr"] = _revenue_at_t0(grid, dataset, spec)
    grid = grid.loc[:, ["client_id", "T0", "mrr"]].sort_values(
        "client_id", kind="stable", ignore_index=True
    )
    return ScoringSet(grid=grid, features=_feature_matrix(grid, dataset, spec), date=date)


def build_training_set(dataset: Dataset, spec: GridSpec) -> TrainingSet:
    """Build the grid, the target and the feature matrix.

    Args:
        dataset: the two contract tables.
        spec: shape of the grid.

    Returns:
        The three aligned pieces.
    """
    grid = build_grid(dataset, spec)
    if grid.empty:
        return TrainingSet(grid=grid, target=pd.Series(dtype="int64"), features=pd.DataFrame())
    return TrainingSet(grid=grid, target=grid["y"], features=_feature_matrix(grid, dataset, spec))


def _feature_matrix(grid: pd.DataFrame, dataset: Dataset, spec: GridSpec) -> pd.DataFrame:
    """Return the feature matrix of a grid, shared by training and scoring."""
    features = build_window_features(
        grid[["client_id", "T0"]],
        dataset.events,
        spec.windows_days,
        resolution=spec.resolution,
    )
    # Structural columns. They are known at ``T0`` and carry no future: the age
    # is a difference against ``T0`` itself, and the revenue was read from the
    # journal strictly before ``T0`` by ``build_grid``.
    started = (
        dataset.accounts.set_index("client_id")["date_debut_contrat"]
        .reindex(grid["client_id"])
        .to_numpy(dtype=f"datetime64[{spec.resolution}]")
    )
    structural = pd.DataFrame(
        {
            "anciennete_jours": (
                (grid["T0"].dt.tz_localize(None).to_numpy() - started) / np.timedelta64(1, "D")
            ).astype("float64"),
            "mrr": grid["mrr"].to_numpy(),
        },
        index=grid.index,
    )
    return pd.concat([features, structural], axis=1)
