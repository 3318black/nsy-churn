"""Read-only access to what the pipeline wrote, for the interface of lot 7.

The interface never trains, scores or recomputes a measure. Every figure it shows
is read from a file the pipeline produced: the export of lot 6 and its
contributions, the evaluation report of lot 5, and the contract journal for the
history of an account. This module is the only place that knows where those files
are and what they look like, so the application stays a thin display layer.

**The history of an account stops strictly before the scoring date.** Showing the
events that followed would show what the model could not know, and invite reading
the future into the ranking. Decision D21.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from churn.pipeline.schemas import (
    CONTRIBUTION_COLUMNS,
    CONTRIBUTIONS_SUFFIX,
    EXPORT_COLUMNS,
    EXPORT_FILE_PREFIX,
    PARQUET_METADATA_KEY,
)

__all__ = [
    "EVENT_COLUMNS",
    "PERIODS_FILE",
    "SUMMARY_FILE",
    "ExportIdentity",
    "LoadedExport",
    "account_contributions",
    "account_history",
    "evaluation_periods",
    "evaluation_summary",
    "export_dates",
    "load_export",
    "report_banner",
    "weekly_activity",
]

#: File of the averaged measures written by the evaluation report.
SUMMARY_FILE = "evaluation_summary.csv"

#: File of the precision of each scoring period written by the evaluation report.
PERIODS_FILE = "evaluation_precision_per_period.csv"

#: Columns of the contract journal the history shows.
EVENT_COLUMNS = ("client_id", "event_ts", "event_type", "event_value")

_EXPORT_NAME = re.compile(rf"^{EXPORT_FILE_PREFIX}(\d{{4}}-\d{{2}}-\d{{2}})\.parquet$")


@dataclass(frozen=True, slots=True)
class ExportIdentity:
    """What identifies an export, read from its metadata.

    Attributes:
        batch_run_id: identifier of the run.
        date_scoring: the scoring date.
        model_version: version of the model.
        significance_threshold: threshold the factors were filtered with.
        source_label: label of the data source.
        is_synthetic: whether the data is simulated.
        row_count: number of scored accounts.
    """

    batch_run_id: str
    date_scoring: date
    model_version: str
    significance_threshold: float | None
    source_label: str
    is_synthetic: bool
    row_count: int

    @classmethod
    def from_metadata(cls, payload: dict[str, object]) -> ExportIdentity:
        """Build the identity from the JSON stored in the Parquet metadata."""
        threshold = payload.get("significance_threshold")
        return cls(
            batch_run_id=str(payload["batch_run_id"]),
            date_scoring=date.fromisoformat(str(payload["date_scoring"])),
            model_version=str(payload["model_version"]),
            significance_threshold=None if threshold is None else float(str(threshold)),
            source_label=str(payload["source_label"]),
            is_synthetic=bool(payload["is_synthetic"]),
            row_count=int(str(payload["row_count"])),
        )


@dataclass(frozen=True, slots=True)
class LoadedExport:
    """An export as the interface reads it.

    Attributes:
        rows: the exported rows, in rank order.
        contributions: the contributions by origin, empty when not exported.
        identity: what identifies the export.
    """

    rows: pd.DataFrame
    contributions: pd.DataFrame
    identity: ExportIdentity


def export_dates(directory: Path) -> list[date]:
    """Return the scoring dates exported under ``directory``, latest first.

    Args:
        directory: the export directory of one source.

    Returns:
        The dates, empty when the directory does not exist yet.
    """
    if not directory.is_dir():
        return []
    found = [
        date.fromisoformat(match.group(1))
        for path in directory.iterdir()
        if (match := _EXPORT_NAME.match(path.name))
    ]
    return sorted(found, reverse=True)


def load_export(directory: Path, day: date) -> LoadedExport:
    """Read the export of one scoring date.

    Args:
        directory: the export directory of one source.
        day: the scoring date.

    Returns:
        The rows, the contributions when present, and the identity.

    Raises:
        ValueError: when the file carries no identity or breaks the column contract.
    """
    stem = f"{EXPORT_FILE_PREFIX}{day.isoformat()}"
    table = pq.read_table(directory / f"{stem}.parquet")
    metadata = table.schema.metadata or {}
    if PARQUET_METADATA_KEY not in metadata:
        message = f"export {stem} carries no batch identity: it was not written by the pipeline"
        raise ValueError(message)
    rows = table.to_pandas()
    if tuple(rows.columns) != EXPORT_COLUMNS:
        message = f"export {stem} columns {list(rows.columns)} differ from the contract"
        raise ValueError(message)

    contributions_path = directory / f"{stem}{CONTRIBUTIONS_SUFFIX}.parquet"
    contributions = (
        pd.read_parquet(contributions_path)
        if contributions_path.is_file()
        else pd.DataFrame(columns=list(CONTRIBUTION_COLUMNS))
    )
    identity = ExportIdentity.from_metadata(json.loads(metadata[PARQUET_METADATA_KEY]))
    return LoadedExport(rows=rows, contributions=contributions, identity=identity)


def account_contributions(export: LoadedExport, client_id: str) -> pd.DataFrame:
    """Return the contributions of one account, strongest first."""
    selected = export.contributions.loc[export.contributions["client_id"] == client_id]
    return selected.sort_values(
        ["contribution", "variable_origine"],
        ascending=[False, True],
        kind="stable",
        ignore_index=True,
    )


def account_history(events_path: Path, client_id: str, before: pd.Timestamp) -> pd.DataFrame:
    """Return the events of one account strictly before a date.

    Args:
        events_path: the contract journal of the source, in Parquet.
        client_id: the account.
        before: timezone aware bound, the scoring date. Excluded.

    Returns:
        The events in chronological order, empty when the journal is absent,
        as it is for the synthetic source, generated on the fly.
    """
    if not events_path.is_file():
        return pd.DataFrame(columns=list(EVENT_COLUMNS))
    events = pd.read_parquet(
        events_path, columns=list(EVENT_COLUMNS), filters=[("client_id", "==", client_id)]
    )
    events = events.loc[events["event_ts"] < before]
    return events.sort_values("event_ts", kind="stable", ignore_index=True)


def weekly_activity(history: pd.DataFrame, event_types: Collection[str]) -> pd.DataFrame:
    """Count the events of an account per week and type, for a chart.

    This is a display aggregate of raw events, not a model measure.

    Args:
        history: the events of one account.
        event_types: the types to count.

    Returns:
        Columns ``semaine``, ``event_type``, ``nombre`` and ``total``.
    """
    selected = history.loc[history["event_type"].isin(list(event_types))]
    if selected.empty:
        return pd.DataFrame(columns=["semaine", "event_type", "nombre", "total"])
    weeks = selected["event_ts"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    return (
        selected.assign(semaine=weeks)
        .groupby(["semaine", "event_type"], as_index=False)
        .agg(nombre=("event_value", "size"), total=("event_value", "sum"))
    )


def _read_report(path: Path) -> pd.DataFrame:
    """Read a CSV of the evaluation report, skipping its source banner."""
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path, comment="#")


def report_banner(directory: Path) -> str | None:
    """Return the source statement opening the evaluation report, when present."""
    path = directory / SUMMARY_FILE
    if not path.is_file():
        return None
    first = path.read_text(encoding="utf-8").splitlines()[0]
    return first.removeprefix("#").strip()


def evaluation_summary(directory: Path) -> pd.DataFrame:
    """Return the averaged measures of every ranking, empty when absent."""
    return _read_report(directory / SUMMARY_FILE)


def evaluation_periods(directory: Path) -> pd.DataFrame:
    """Return the precision of every ranking per scoring period, empty when absent."""
    periods = _read_report(directory / PERIODS_FILE)
    if not periods.empty:
        periods["period_start"] = pd.to_datetime(periods["period_start"])
    return periods
