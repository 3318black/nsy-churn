"""Vectorised check of the data contract invariants.

Every invariant of ``docs/data-contract.md`` sections 1 and 2 is checked here,
against any source, real or simulated. Three rules drive this module.

1. **Failure is blocking and never silent.** A faulty row is reported, never
   repaired. Repairing in place would hide a broken adapter behind a clean run.
2. **Every invariant is checked independently and the report accumulates them.**
   Stopping at the first breach would force one run per defect, which is
   unworkable on a dataset holding millions of rows.
3. **Everything is vectorised.** No Python loop walks the rows. The real dataset
   holds 21.5 million transactions.

The report names the table, the invariant, the number of offending rows and a
sample of the identifiers involved. On a multi million row frame, a bare
"validation failed" is unusable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from churn.data.schemas import (
    ACCOUNTS_SCHEMA,
    EVENTS_SCHEMA,
    ColumnKind,
    Dataset,
    DatetimeResolution,
    TableSchema,
)

__all__ = [
    "ContractViolation",
    "ValidationError",
    "ValidationReport",
    "validate_accounts",
    "validate_dataset",
    "validate_events",
]

#: How many offending identifiers a violation carries as an illustration.
SAMPLE_SIZE = 5


@dataclass(frozen=True, slots=True)
class ContractViolation:
    """One breached invariant.

    Attributes:
        table: name of the table the invariant belongs to.
        invariant: stable identifier of the invariant, usable in a test.
        message: human readable statement of what is wrong.
        count: number of offending rows, or of offending columns for a
            structural breach.
        sample: a few offending identifiers, as an illustration.
    """

    table: str
    invariant: str
    message: str
    count: int
    sample: tuple[str, ...] = ()

    def __str__(self) -> str:
        """Return the one line rendering used in the report."""
        head = f"[{self.table}] {self.invariant}: {self.message} ({self.count} rows)"
        if not self.sample:
            return head
        return f"{head}, e.g. {', '.join(self.sample)}"


@dataclass(slots=True)
class ValidationReport:
    """Outcome of a validation run.

    Attributes:
        violations: every breached invariant, in the order they were checked.
    """

    violations: list[ContractViolation] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Whether the dataset conforms to the contract."""
        return not self.violations

    @property
    def invariants(self) -> tuple[str, ...]:
        """Identifiers of the breached invariants, for assertions in tests."""
        return tuple(violation.invariant for violation in self.violations)

    def add(self, violation: ContractViolation) -> None:
        """Record one breached invariant."""
        self.violations.append(violation)

    def check_rows(
        self,
        frame: pd.DataFrame,
        mask: pd.Series,
        *,
        table: str,
        invariant: str,
        message: str,
    ) -> None:
        """Record a violation when ``mask`` selects at least one row.

        Args:
            frame: frame the mask applies to.
            mask: boolean mask selecting the offending rows.
            table: name of the table.
            invariant: stable identifier of the invariant.
            message: human readable statement.
        """
        count = int(mask.sum())
        if not count:
            return
        self.add(
            ContractViolation(
                table=table,
                invariant=invariant,
                message=message,
                count=count,
                sample=_sample_ids(frame, mask),
            )
        )

    def extend(self, other: ValidationReport) -> None:
        """Merge another report into this one."""
        self.violations.extend(other.violations)

    def render(self) -> str:
        """Return the multi line rendering of the report."""
        if self.is_valid:
            return "dataset conforms to the contract"
        lines = [f"{len(self.violations)} contract violation(s):"]
        lines.extend(f"  - {violation}" for violation in self.violations)
        return "\n".join(lines)

    def raise_if_invalid(self) -> None:
        """Raise :class:`ValidationError` when at least one invariant is breached."""
        if not self.is_valid:
            raise ValidationError(self)


class ValidationError(RuntimeError):
    """Raised when a dataset breaches the contract.

    Attributes:
        report: the full report, so a caller can inspect the invariants rather
            than parse the message.
    """

    def __init__(self, report: ValidationReport) -> None:
        super().__init__(report.render())
        self.report = report


def _sample_ids(frame: pd.DataFrame, mask: pd.Series) -> tuple[str, ...]:
    """Return a few client identifiers matching ``mask``, as an illustration."""
    if "client_id" not in frame.columns:
        return ()
    offending = frame.loc[mask, "client_id"]
    return tuple(str(value) for value in offending.head(SAMPLE_SIZE).tolist())


def _check_structure(report: ValidationReport, frame: pd.DataFrame, schema: TableSchema) -> bool:
    """Check the column level contract of a table.

    A missing core column is a breach. A missing optional column is not: a source
    that does not provide it stays conformant, the features that depend on it are
    simply not built.

    Returns:
        Whether the structure allows the value level invariants to be checked.
    """
    missing = schema.missing_core_columns(frame.columns)
    if missing:
        report.add(
            ContractViolation(
                table=schema.name,
                invariant="core_columns_present",
                message=f"mandatory column(s) missing: {', '.join(missing)}",
                count=len(missing),
            )
        )

    undeclared = tuple(name for name in frame.columns if name not in schema.column_names)
    if undeclared:
        report.add(
            ContractViolation(
                table=schema.name,
                invariant="no_undeclared_column",
                message=f"column(s) outside the contract: {', '.join(undeclared)}",
                count=len(undeclared),
            )
        )

    for name in schema.declared_columns(frame.columns):
        if schema.column(name).nullable:
            continue
        report.check_rows(
            frame,
            frame[name].isna(),
            table=schema.name,
            invariant=f"{name}_not_null",
            message=f"'{name}' holds a missing value",
        )

    for spec in schema.columns:
        if spec.categories is None or spec.name not in frame.columns:
            continue
        values = frame[spec.name]
        unknown = values.notna() & ~values.astype("str").isin(spec.categories)
        report.check_rows(
            frame,
            unknown,
            table=schema.name,
            invariant=f"{spec.name}_in_nomenclature",
            message=(
                f"'{spec.name}' holds a value outside the closed nomenclature "
                f"({', '.join(spec.categories)})"
            ),
        )

    return not missing


def _check_timezone_aware(
    report: ValidationReport, frame: pd.DataFrame, schema: TableSchema
) -> None:
    """Check that every timestamp column carries a timezone.

    A naive timestamp is refused rather than localised, because guessing the zone
    would silently shift every window of the pipeline.
    """
    for spec in schema.columns:
        if spec.kind is not ColumnKind.TIMESTAMP or spec.name not in frame.columns:
            continue
        dtype = frame[spec.name].dtype
        if getattr(dtype, "tz", None) is None:
            report.add(
                ContractViolation(
                    table=schema.name,
                    invariant=f"{spec.name}_timezone_aware",
                    message=(
                        f"'{spec.name}' carries no timezone (dtype {dtype}), "
                        f"a naive timestamp is refused, never localised by guess"
                    ),
                    count=len(frame),
                )
            )


def validate_accounts(
    accounts: pd.DataFrame,
    *,
    now: datetime | None = None,
) -> ValidationReport:
    """Check the invariants of the ``accounts`` table.

    Args:
        accounts: the account reference table.
        now: execution instant, used to refuse dates in the future. Defaults to
            the current UTC instant. Injectable so a test stays deterministic.

    Returns:
        The report, breached invariants included.
    """
    report = ValidationReport()
    schema = ACCOUNTS_SCHEMA
    now = now or datetime.now(UTC)

    if not _check_structure(report, accounts, schema):
        return report
    _check_timezone_aware(report, accounts, schema)

    duplicated = accounts["client_id"].duplicated(keep=False)
    report.check_rows(
        accounts,
        duplicated,
        table=schema.name,
        invariant="client_id_unique",
        message="'client_id' is duplicated, it is the primary key",
    )

    started = accounts["date_debut_contrat"]
    ended = accounts["date_resiliation"]
    report.check_rows(
        accounts,
        ended.notna() & (ended <= started),
        table=schema.name,
        invariant="resiliation_after_debut",
        message="'date_resiliation' is not strictly after 'date_debut_contrat'",
    )

    for column in ("date_debut_contrat", "date_resiliation"):
        values = accounts[column]
        if getattr(values.dtype, "tz", None) is None:
            continue
        report.check_rows(
            accounts,
            values.notna() & (values > pd.Timestamp(now)),
            table=schema.name,
            invariant=f"{column}_not_in_future",
            message=f"'{column}' is later than the execution instant",
        )

    report.check_rows(
        accounts,
        accounts["mrr"] < 0,
        table=schema.name,
        invariant="mrr_non_negative",
        message="'mrr' is negative",
    )

    return report


def validate_events(events: pd.DataFrame, accounts: pd.DataFrame) -> ValidationReport:
    """Check the invariants of the ``events`` table.

    Args:
        events: the journal of dated events.
        accounts: the account reference table, needed for the referential and
            the contract window invariants.

    Returns:
        The report, breached invariants included.
    """
    report = ValidationReport()
    schema = EVENTS_SCHEMA

    if not _check_structure(report, events, schema):
        return report
    _check_timezone_aware(report, events, schema)

    if "client_id" in accounts.columns:
        orphan = ~events["client_id"].isin(set(accounts["client_id"]))
        report.check_rows(
            events,
            orphan,
            table=schema.name,
            invariant="client_id_exists_in_accounts",
            message="'client_id' has no counterpart in accounts",
        )

    window_columns = {"client_id", "date_debut_contrat", "date_resiliation"}
    if not window_columns.issubset(accounts.columns):
        return report
    if getattr(events["event_ts"].dtype, "tz", None) is None:
        # The window comparison needs an aware series on both sides. The breach
        # is already reported by the timezone invariant above.
        return report

    bounds = accounts.set_index("client_id")[["date_debut_contrat", "date_resiliation"]]
    joined = events[["client_id", "event_ts"]].join(bounds, on="client_id")
    started = joined["date_debut_contrat"]
    ended = joined["date_resiliation"]

    report.check_rows(
        events,
        started.notna() & (joined["event_ts"] < started),
        table=schema.name,
        invariant="event_after_contract_start",
        message="'event_ts' is earlier than the start of the account contract",
    )
    report.check_rows(
        events,
        ended.notna() & (joined["event_ts"] > ended),
        table=schema.name,
        invariant="event_before_resiliation",
        message="'event_ts' is later than the termination of the account",
    )

    return report


def validate_dataset(
    dataset: Dataset,
    *,
    now: datetime | None = None,
    resolution: DatetimeResolution | None = None,
) -> ValidationReport:
    """Check both tables of a dataset against the contract.

    Args:
        dataset: the pair of contract tables.
        now: execution instant, used to refuse dates in the future.
        resolution: expected timestamp resolution. When given, a column carrying
            another resolution is reported. Mixing ``[us]`` and ``[ns]`` makes
            ``merge_asof`` fail later, see section 3.5 of the data contract.

    Returns:
        The cumulated report of both tables.
    """
    report = ValidationReport()
    report.extend(validate_accounts(dataset.accounts, now=now))
    report.extend(validate_events(dataset.events, dataset.accounts))

    if resolution is not None:
        for frame, schema in ((dataset.accounts, ACCOUNTS_SCHEMA), (dataset.events, EVENTS_SCHEMA)):
            for spec in schema.timestamp_columns:
                if spec.name not in frame.columns:
                    continue
                dtype = frame[spec.name].dtype
                unit = getattr(dtype, "unit", None)
                if unit is not None and unit != resolution:
                    report.add(
                        ContractViolation(
                            table=schema.name,
                            invariant=f"{spec.name}_resolution",
                            message=(
                                f"'{spec.name}' carries resolution '{unit}' where "
                                f"'{resolution}' is expected, mixing resolutions "
                                f"makes merge_asof fail"
                            ),
                            count=len(frame),
                        )
                    )

    return report
