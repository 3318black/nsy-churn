"""Destinations of a scoring batch, decision D8.

A destination writes what it receives and never transforms a value. Four are
provided.

Parquet
    The source of truth: typed, compressed, and carrying the batch identity and
    the data source in its metadata.
CSV
    For the spreadsheet a salesperson opens. Excel under Windows breaks accents
    without a byte order mark, hence ``utf-8-sig``; a French locale reads ``;`` as
    the separator and ``,`` as the decimal mark. All three come from the
    configuration.
JSON
    For a dedicated front end, should one ever read the export without touching
    the pipeline, decision D15. The batch identity and the source travel with the
    rows.
Contributions
    The contribution of every origin variable for every account, in Parquet, so
    that the interface of lot 7 explains a rank without recomputing it, D21.

**Adding a destination means implementing :class:`Sink`, nothing else.** The
pipeline takes any sequence of sinks. A test checks it with a destination that
only exists inside the test.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from churn.config import ExportConfig
from churn.pipeline.schemas import CONTRIBUTIONS_SUFFIX, EXPORT_FILE_PREFIX, PARQUET_METADATA_KEY
from churn.pipeline.scoring import ScoringBatch

__all__ = [
    "PARQUET_METADATA_KEY",
    "ContributionsSink",
    "CsvSink",
    "JsonSink",
    "ParquetSink",
    "Sink",
    "batch_identity",
    "default_sinks",
    "export_stem",
    "write_batch",
]


class Sink(Protocol):
    """Anything able to write a scoring batch."""

    name: str

    def write(self, batch: ScoringBatch, directory: Path) -> Path:
        """Write the batch under ``directory`` and return what was written."""
        ...


def export_stem(batch: ScoringBatch) -> str:
    """Return the file name of a batch, without extension."""
    return f"{EXPORT_FILE_PREFIX}{batch.date_scoring.isoformat()}"


def batch_identity(batch: ScoringBatch) -> dict[str, object]:
    """Return what identifies a batch, as it travels with the rows."""
    return {
        "batch_run_id": str(batch.batch_run_id),
        "date_scoring": batch.date_scoring.isoformat(),
        "model_version": batch.model_version,
        "significance_threshold": batch.significance_threshold,
        "source_label": batch.source_label,
        "is_synthetic": batch.is_synthetic,
        "row_count": len(batch.rows),
    }


def _write_parquet(frame: pd.DataFrame, batch: ScoringBatch, path: Path) -> Path:
    """Write a frame as Parquet, with the batch identity in the file metadata."""
    table = pa.Table.from_pandas(frame, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    identity = json.dumps(batch_identity(batch), sort_keys=True)
    metadata[PARQUET_METADATA_KEY] = identity.encode("utf-8")
    pq.write_table(table.replace_schema_metadata(metadata), path)
    return path


class ParquetSink:
    """Writes the rows as Parquet, the source of truth."""

    name = "parquet"

    def write(self, batch: ScoringBatch, directory: Path) -> Path:
        """Write the rows, with the batch identity in the file metadata."""
        return _write_parquet(batch.rows, batch, directory / f"{export_stem(batch)}.parquet")


class ContributionsSink:
    """Writes the contributions as Parquet, for the interface, decision D21."""

    name = "contributions"

    def write(self, batch: ScoringBatch, directory: Path) -> Path:
        """Write the contributions next to the rows, under the same identity."""
        path = directory / f"{export_stem(batch)}{CONTRIBUTIONS_SUFFIX}.parquet"
        return _write_parquet(batch.contributions, batch, path)


class CsvSink:
    """Writes the batch as CSV, for a spreadsheet."""

    name = "csv"

    def __init__(self, encoding: str, separator: str, decimal: str) -> None:
        """Initialise the sink.

        Args:
            encoding: text encoding, ``utf-8-sig`` so that Excel reads accents.
            separator: column separator.
            decimal: decimal mark.
        """
        self._encoding = encoding
        self._separator = separator
        self._decimal = decimal

    def write(self, batch: ScoringBatch, directory: Path) -> Path:
        """Write the rows. Line endings are fixed, so every system writes the same bytes."""
        path = directory / f"{export_stem(batch)}.csv"
        batch.rows.to_csv(
            path,
            sep=self._separator,
            decimal=self._decimal,
            encoding=self._encoding,
            index=False,
            lineterminator="\r\n",
        )
        return path


class JsonSink:
    """Writes the batch as JSON, for a dedicated front end."""

    name = "json"

    def write(self, batch: ScoringBatch, directory: Path) -> Path:
        """Write the batch identity followed by the rows."""
        path = directory / f"{export_stem(batch)}.json"
        records = batch.rows.assign(
            date_scoring=[day.isoformat() for day in batch.rows["date_scoring"]]
        ).to_dict(orient="records")
        payload = {**batch_identity(batch), "rows": records}
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path


def default_sinks(export: ExportConfig) -> list[Sink]:
    """Return the four destinations of the export, configured."""
    return [
        ParquetSink(),
        CsvSink(export.csv_encoding, export.csv_separator, export.csv_decimal),
        JsonSink(),
        ContributionsSink(),
    ]


def write_batch(batch: ScoringBatch, directory: Path, sinks: Sequence[Sink]) -> list[Path]:
    """Write a batch to every destination.

    Args:
        batch: the scored batch.
        directory: destination directory, created when missing.
        sinks: the destinations, any implementation of :class:`Sink`.

    Returns:
        What each destination wrote, in order.
    """
    directory.mkdir(parents=True, exist_ok=True)
    return [sink.write(batch, directory) for sink in sinks]
