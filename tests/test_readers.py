"""Tests of the read-only access the interface relies on."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from churn.interface.readers import (
    EVENT_COLUMNS,
    account_history,
    evaluation_periods,
    evaluation_summary,
    export_dates,
    load_export,
    report_banner,
    weekly_activity,
)
from churn.pipeline.schemas import EXPORT_COLUMNS


def _events() -> pd.DataFrame:
    """Return a tiny journal of two accounts."""
    return pd.DataFrame(
        {
            "client_id": ["A", "A", "A", "A", "B"],
            "event_ts": pd.to_datetime(
                [
                    "2025-01-06 10:00",
                    "2025-01-08 10:00",
                    "2025-01-13 09:00",
                    "2025-01-20 00:00",
                    "2025-01-07 10:00",
                ],
                utc=True,
            ).as_unit("us"),
            "event_type": ["connexion"] * 5,
            "event_value": [3.0, 4.0, 5.0, 6.0, 1.0],
        }
    )


def test_export_dates_list_the_rows_files_latest_first(tmp_path: Path) -> None:
    """The contributions file and unrelated files are not scoring dates."""
    for name in (
        "scoring_2025-01-06.parquet",
        "scoring_2025-01-13.parquet",
        "scoring_2025-01-13_contributions.parquet",
        "scoring_2025-01-13.csv",
        "notes.txt",
    ):
        (tmp_path / name).write_bytes(b"")
    assert export_dates(tmp_path) == [date(2025, 1, 13), date(2025, 1, 6)]


def test_a_missing_export_directory_has_no_date(tmp_path: Path) -> None:
    """Before the first scoring run, the interface simply finds nothing."""
    assert export_dates(tmp_path / "absent") == []


def test_a_file_the_pipeline_did_not_write_is_refused(tmp_path: Path) -> None:
    """Without its batch identity, a file cannot say where it comes from, D2."""
    pd.DataFrame(columns=list(EXPORT_COLUMNS)).to_parquet(tmp_path / "scoring_2025-01-06.parquet")
    with pytest.raises(ValueError, match="identity"):
        load_export(tmp_path, date(2025, 1, 6))


def test_the_history_stops_strictly_before_the_scoring_date(tmp_path: Path) -> None:
    """Decision D21: the sheet shows what the model knew, not what followed."""
    path = tmp_path / "events.parquet"
    _events().to_parquet(path)
    history = account_history(path, "A", pd.Timestamp("2025-01-20", tz="UTC"))
    assert tuple(history.columns) == EVENT_COLUMNS
    assert set(history["client_id"]) == {"A"}
    assert len(history) == 3
    assert history["event_ts"].is_monotonic_increasing


def test_a_missing_journal_yields_an_empty_history(tmp_path: Path) -> None:
    """The synthetic source has no journal on disk, which is not an error."""
    history = account_history(
        tmp_path / "absent.parquet", "A", pd.Timestamp("2025-01-20", tz="UTC")
    )
    assert history.empty
    assert tuple(history.columns) == EVENT_COLUMNS


def test_weekly_activity_counts_events_per_week() -> None:
    """Two events in the week of 6 January, one in the week of 13 January."""
    history = _events().loc[lambda frame: frame["client_id"] == "A"].head(3)
    activity = weekly_activity(history, ["connexion"])
    assert activity["nombre"].tolist() == [2, 1]
    assert activity["total"].tolist() == [7.0, 5.0]
    assert activity["semaine"].tolist() == [pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-13")]


def test_missing_reports_read_as_empty(tmp_path: Path) -> None:
    """Before the first training run, the performance screen finds nothing."""
    assert evaluation_summary(tmp_path).empty
    assert evaluation_periods(tmp_path).empty
    assert report_banner(tmp_path) is None


def test_the_report_banner_is_read_back(tmp_path: Path) -> None:
    """The source statement of the report reaches the screen."""
    (tmp_path / "evaluation_summary.csv").write_text(
        "# Source: KKBox\nscorer,precision_at_k\nxgboost,0.33\n", encoding="utf-8"
    )
    assert report_banner(tmp_path) == "Source: KKBox"
    assert evaluation_summary(tmp_path)["precision_at_k"].tolist() == [0.33]
