"""Single source interface every origin of data implements.

The contract never bends to a source: a source conforms through an adapter. This
module holds that boundary. The KKBox adapter of lot 2 plugs in here without
changing anything downstream, exactly as a company extract would later.

Two things travel with the data and matter beyond loading.

``is_synthetic``
    Reaches the reports, so that a figure obtained on simulated data is always
    labelled as such. Decision D2 rests on this flag.
``horizon_days`` and ``embargo_days``
    Carried by the source profile, because the KKBox horizon is 30 days where the
    default is 60. They are configuration, never constants in the code.

Paths always come from ``config.paths``. No module builds a file path of its own.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from churn.config import AppConfig, SourceProfile
from churn.data.schemas import (
    ACCOUNTS_SCHEMA,
    EVENTS_SCHEMA,
    ColumnKind,
    Dataset,
    DatetimeResolution,
    TableSchema,
)

__all__ = [
    "DataSource",
    "ParquetDataSource",
    "SourceDescription",
    "normalise_frame",
    "read_dataset",
    "write_dataset",
]


@dataclass(frozen=True, slots=True)
class SourceDescription:
    """Identity of a source, as it travels to the reports.

    Attributes:
        key: key of the profile in ``config.sources``, for instance ``kkbox``.
        label: human readable label of the source.
        is_synthetic: whether the data is simulated. Decision D2 makes every
            report state it.
        horizon_days: prediction horizon of this source, in days.
        embargo_days: embargo between training and test, in days.
    """

    key: str
    label: str
    is_synthetic: bool
    horizon_days: int
    embargo_days: int

    @classmethod
    def from_profile(cls, key: str, profile: SourceProfile) -> SourceDescription:
        """Build the description from a configuration profile."""
        return cls(
            key=key,
            label=profile.label,
            is_synthetic=profile.is_synthetic,
            horizon_days=profile.horizon_days,
            embargo_days=profile.embargo_days,
        )


def normalise_frame(
    frame: pd.DataFrame,
    schema: TableSchema,
    resolution: DatetimeResolution,
) -> pd.DataFrame:
    """Return ``frame`` with contract dtypes and a normalised time resolution.

    Normalising here rather than assuming is what prevents the resolution trap of
    pandas 3.0: ``date_range`` yields ``datetime64[us]`` while a construction
    through ``to_timedelta`` may yield ``[ns]``, and ``merge_asof`` refuses to mix
    them. See section 3.5 of the data contract.

    A naive timestamp is left naive on purpose. Localising it by guess would shift
    every window of the pipeline silently, so the validator reports it instead.

    Args:
        frame: the frame to normalise.
        schema: contract of the table.
        resolution: target resolution, from ``features.datetime_resolution``.

    Returns:
        A new frame carrying the declared columns, in contract order.
    """
    columns = schema.declared_columns(frame.columns)
    out = frame.loc[:, list(columns)].copy()
    for name in columns:
        spec = schema.column(name)
        if spec.kind is not ColumnKind.TIMESTAMP:
            continue
        series = out[name]
        if getattr(series.dtype, "tz", None) is None:
            continue
        # ``dt.as_unit`` rather than ``astype`` with an f-string: the dtype is
        # dynamic and the pandas stubs only type the literal overloads.
        out[name] = series.dt.as_unit(resolution)
    return out


def write_dataset(dataset: Dataset, directory: Path) -> dict[str, Path]:
    """Write both tables as Parquet files.

    Args:
        dataset: the pair of contract tables.
        directory: destination directory, created when missing.

    Returns:
        The path of each written table, keyed by table name.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, frame in (
        (ACCOUNTS_SCHEMA.name, dataset.accounts),
        (EVENTS_SCHEMA.name, dataset.events),
    ):
        path = directory / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        written[name] = path
    return written


def read_dataset(directory: Path, resolution: DatetimeResolution) -> Dataset:
    """Read both tables from Parquet files.

    Args:
        directory: directory holding ``accounts.parquet`` and ``events.parquet``.
        resolution: target timestamp resolution.

    Returns:
        The dataset, with contract columns and a normalised resolution.

    Raises:
        FileNotFoundError: when one of the two files is missing.
    """
    frames: dict[str, pd.DataFrame] = {}
    for schema in (ACCOUNTS_SCHEMA, EVENTS_SCHEMA):
        path = directory / f"{schema.name}.parquet"
        if not path.exists():
            message = f"missing table '{schema.name}': {path}"
            raise FileNotFoundError(message)
        frames[schema.name] = normalise_frame(pd.read_parquet(path), schema, resolution)
    return Dataset(
        accounts=frames[ACCOUNTS_SCHEMA.name],
        events=frames[EVENTS_SCHEMA.name],
    )


class DataSource(ABC):
    """Origin of data conforming to the contract.

    An implementation adapts its own files to the two contract tables. It never
    relaxes the contract: a source unable to provide a core column is not
    conformant, and that has to surface rather than be worked around.
    """

    @property
    @abstractmethod
    def description(self) -> SourceDescription:
        """Identity of the source, as it travels to the reports."""

    @abstractmethod
    def load(self) -> Dataset:
        """Return the two contract tables, with normalised dtypes."""


class ParquetDataSource(DataSource):
    """Source reading the two contract tables from a Parquet directory.

    It is the shared tail of every adapter: an adapter converts its raw files
    once, writes them here, and later runs read from Parquet.
    """

    def __init__(
        self,
        directory: Path,
        description: SourceDescription,
        resolution: DatetimeResolution,
    ) -> None:
        """Initialise the source.

        Args:
            directory: directory holding the two Parquet tables.
            description: identity of the source.
            resolution: target timestamp resolution.
        """
        self._directory = directory
        self._description = description
        self._resolution = resolution

    @classmethod
    def from_config(cls, config: AppConfig, subdirectory: str | None = None) -> ParquetDataSource:
        """Build the source of the active profile from the configuration.

        Args:
            config: the loaded configuration.
            subdirectory: optional subdirectory of ``paths.processed``. Defaults
                to the key of the active source, so two sources never collide.

        Returns:
            The configured source.
        """
        key = config.active_source
        directory = config.paths.processed / (subdirectory or key)
        return cls(
            directory=directory,
            description=SourceDescription.from_profile(key, config.active_profile()),
            resolution=config.features.datetime_resolution,
        )

    @property
    def directory(self) -> Path:
        """Directory the tables are read from."""
        return self._directory

    @property
    def description(self) -> SourceDescription:
        """Identity of the source."""
        return self._description

    def load(self) -> Dataset:
        """Read both tables from the Parquet directory."""
        return read_dataset(self._directory, self._resolution)
