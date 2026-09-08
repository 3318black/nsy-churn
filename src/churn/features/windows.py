"""Rolling window aggregates over the event journal.

This is where the risk of the project concentrates. Every value produced here
answers one question: what did we know about this account strictly before ``T0``?
An aggregate that peeks a single day past that boundary makes the whole
evaluation meaningless while every test stays green.

**Three traps were measured on 2026-09-07, on two million events, and each one
produced wrong rows without raising anything.**

Mixed time resolutions
    Under pandas 3.0 several resolutions coexist. ``merge_asof`` refuses to join
    ``datetime64[us]`` with ``datetime64[ns]``. That one is the lucky case: it
    raises.
Reindexing by ``merge_asof``
    The function returns a reordered frame. A ``sort_index`` does not restore the
    original order, so columns end up attached to the wrong rows. An explicit
    order column is kept and sorted back on.
Duplicated timestamps
    When several events of one account share a timestamp, ``merge_asof`` does not
    guarantee the last row of the group. The cumulative value picked is then a
    partial one. **This single omission produced 10.5% of wrong rows.** The fix
    is to aggregate to the maximum cumulative value per ``(client_id, event_ts)``
    before any join.

The method itself is a cumulative difference. Counting events between two bounds
by filtering would cost one pass per bound and per account. Instead the journal
is cumulated once per account, then read at both bounds through an as of join,
and the window is their difference. Four joins cover every window and every
event family at once, rather than one join per family and per window.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from churn.data.schemas import DatetimeResolution, EventType

__all__ = [
    "AggregateKind",
    "WindowFeatures",
    "build_window_features",
    "cumulative_journal",
    "read_at_bound",
]

#: Suffix separating a feature name from the window it covers.
WINDOW_SUFFIX = "j"


class AggregateKind:
    """Aggregates computed per event family and per window.

    ``count`` answers how often something happened, ``sum`` how much of it. Both
    are needed: three support tickets is not the same signal as one ticket of
    triple severity.
    """

    COUNT = "count"
    SUM = "sum"


class WindowFeatures:
    """Names of the produced columns, so no module spells them by hand."""

    @staticmethod
    def column(kind: str, event_type: str, window_days: int) -> str:
        """Return the name of one window feature."""
        return f"{kind}_{event_type}_{window_days}{WINDOW_SUFFIX}"

    @staticmethod
    def trend(kind: str, event_type: str, window_days: int) -> str:
        """Return the name of one trend feature.

        A level describes a customer, a break describes a risk. The trend
        compares a window against the one immediately before it.
        """
        return f"trend_{kind}_{event_type}_{window_days}{WINDOW_SUFFIX}"


def cumulative_journal(
    events: pd.DataFrame,
    event_types: Sequence[str],
    resolution: DatetimeResolution = "us",
) -> pd.DataFrame:
    """Return the per account cumulative journal, one row per distinct timestamp.

    Args:
        events: the contract event journal.
        event_types: families to cumulate, usually those actually present.
        resolution: timestamp resolution imposed on the output.

    Returns:
        A frame with ``client_id``, ``event_ts`` and one cumulative column per
        family and per aggregate, sorted by timestamp.
    """
    frame = events.loc[events["event_type"].isin(event_types)].copy()
    frame["event_ts"] = frame["event_ts"].dt.as_unit(resolution)

    wide = pd.DataFrame(
        {"client_id": frame["client_id"].to_numpy(), "event_ts": frame["event_ts"].to_numpy()}
    )
    values = frame["event_value"].fillna(0.0).to_numpy()
    for event_type in event_types:
        belongs = (frame["event_type"] == event_type).to_numpy()
        wide[f"{AggregateKind.COUNT}_{event_type}"] = belongs.astype("float64")
        wide[f"{AggregateKind.SUM}_{event_type}"] = np.where(belongs, values, 0.0)

    # Aggregate before cumulating: several events may share one timestamp, and a
    # later ``merge_asof`` would otherwise pick a partial cumulative value. This
    # is the omission that produced 10.5% of wrong rows in the measurement.
    measure_columns = [column for column in wide.columns if column not in ("client_id", "event_ts")]
    per_instant = wide.groupby(["client_id", "event_ts"], as_index=False, sort=True)[
        measure_columns
    ].sum()

    cumulated = per_instant.copy()
    cumulated[measure_columns] = per_instant.groupby("client_id", sort=False)[
        measure_columns
    ].cumsum()
    return cumulated.sort_values("event_ts", kind="stable", ignore_index=True)


def read_at_bound(
    grid: pd.DataFrame,
    journal: pd.DataFrame,
    offset_days: int,
    measure_columns: Sequence[str],
) -> pd.DataFrame:
    """Read the cumulative journal at ``T0 - offset_days``, per grid row.

    The bound is strict: an event landing exactly on it is excluded, because a
    feature at ``T0`` may only use what happened strictly before ``T0``.

    Args:
        grid: the observation grid, with ``client_id`` and ``T0``.
        journal: the cumulative journal.
        offset_days: days subtracted from ``T0``.
        measure_columns: cumulative columns to read.

    Returns:
        The cumulative values, one row per grid row, in grid order.
    """
    bounds = grid[["client_id"]].copy()
    # The resolution is re imposed after the arithmetic: subtracting a Timedelta
    # can change it, and merge_asof refuses to mix two resolutions.
    resolution = grid["T0"].dt.unit
    bounds["bound"] = (grid["T0"] - pd.Timedelta(days=offset_days)).dt.as_unit(resolution)
    # Explicit order column: merge_asof reindexes, and sort_index would not
    # restore the original order, attaching columns to the wrong rows.
    bounds["_row"] = np.arange(len(bounds))
    bounds = bounds.sort_values("bound", kind="stable", ignore_index=True)

    merged = pd.merge_asof(
        bounds,
        journal[["client_id", "event_ts", *measure_columns]],
        left_on="bound",
        right_on="event_ts",
        by="client_id",
        direction="backward",
        allow_exact_matches=False,
    ).sort_values("_row", kind="stable", ignore_index=True)
    return merged[list(measure_columns)].fillna(0.0)


def build_window_features(
    grid: pd.DataFrame,
    events: pd.DataFrame,
    windows_days: Sequence[int],
    event_types: Sequence[str] | None = None,
    resolution: DatetimeResolution = "us",
) -> pd.DataFrame:
    """Build every rolling window feature for an observation grid.

    Args:
        grid: the observation grid, with ``client_id`` and ``T0``.
        events: the contract event journal.
        windows_days: window lengths, in days.
        event_types: families to cover. Defaults to those present in ``events``,
            since no source fills the whole nomenclature.
        resolution: timestamp resolution.

    Returns:
        The features, one row per grid row, in grid order.
    """
    if event_types is None:
        event_types = sorted(set(events["event_type"]) & {member.value for member in EventType})
    if not event_types or grid.empty:
        return pd.DataFrame(index=grid.index)

    journal = cumulative_journal(events, event_types, resolution)
    measure_columns = [
        column for column in journal.columns if column not in ("client_id", "event_ts")
    ]

    # Every bound needed by the windows and their trends, read once each.
    offsets = sorted({0, *windows_days, *(window * 2 for window in windows_days)})
    at_bound = {offset: read_at_bound(grid, journal, offset, measure_columns) for offset in offsets}

    # Columns are collected then assembled in one go. Assigning them one by one
    # fragments the frame, which pandas rightly complains about at this width.
    columns: dict[str, np.ndarray] = {}
    for window in windows_days:
        recent = at_bound[0].to_numpy() - at_bound[window].to_numpy()
        previous = at_bound[window].to_numpy() - at_bound[window * 2].to_numpy()
        for position, column in enumerate(measure_columns):
            kind, event_type = column.split("_", 1)
            columns[WindowFeatures.column(kind, event_type, window)] = recent[:, position]
            # Ratio of the two adjacent windows. A break shows here where a level
            # would not: an account may keep its volume while its composition
            # collapses. One is added to both sides so that a window without any
            # event yields a neutral ratio rather than an infinity.
            columns[WindowFeatures.trend(kind, event_type, window)] = (
                recent[:, position] + 1.0
            ) / (previous[:, position] + 1.0)
    return pd.DataFrame(columns, index=grid.index)
