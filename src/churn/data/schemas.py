"""Executable declaration of the data contract.

This module is the single place where ``docs/data-contract.md`` sections 1 and 2
become code: the two input tables, their columns, and the closed nomenclature of
event types. Any source of data, real or simulated, conforms to what is declared
here. The contract never bends to a source, a source conforms through an adapter.

Two properties are declared separately for every column, because they answer two
different questions.

``requirement``
    Must the *column* be present in the frame? A core column is mandatory and its
    absence is an error. An optional column may be missing, and a source that does
    not provide it stays conformant: the features that depend on it are simply not
    built. ``nb_licences`` is the only optional column of the contract.
``nullable``
    May a *value* be missing inside the column? ``date_resiliation`` is null for an
    active account and ``event_value`` is null when the event type carries no
    payload. Every other column refuses a missing value.

**Pydantic declares the schema, it never walks the rows.** The real dataset holds
21.5 million transactions, so a row by row validation would be unusable. The record
models below carry the types and the contract metadata; the effective checks are
vectorised with pandas in :mod:`churn.data.validate`.

Timestamps are declared as timezone aware, in UTC, and their resolution comes from
``config.features.datetime_resolution``. Under pandas 3.0 several resolutions
coexist and mixing ``datetime64[us]`` with ``datetime64[ns]`` makes ``merge_asof``
fail, which is why the resolution is normalised at ingestion rather than assumed.
See section 3.5 of the data contract.

The two date columns of ``accounts`` are timezone aware as well, which is stricter
than the wording of the contract. The reason is mechanical: the events invariant
compares ``event_ts`` with ``date_debut_contrat`` and ``date_resiliation``, and
pandas refuses to compare an aware timestamp with a naive one. Requiring the
timezone on both tables is what makes that invariant checkable at all.
"""

from __future__ import annotations

import types
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import (
    Annotated,
    Any,
    Final,
    Literal,
    Union,
    get_args,
    get_origin,
)

import pandas as pd
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from churn.config import FeatureSource

__all__ = [
    "ACCOUNTS_SCHEMA",
    "ACCOUNTS_TABLE",
    "EVENTS_SCHEMA",
    "EVENTS_TABLE",
    "EVENT_FAMILIES",
    "TABLE_SCHEMAS",
    "AccountRecord",
    "AcquisitionChannel",
    "ColumnContract",
    "ColumnKind",
    "ColumnRequirement",
    "ColumnSpec",
    "ContractType",
    "Dataset",
    "DatetimeResolution",
    "EventRecord",
    "EventType",
    "Segment",
    "TableSchema",
]

#: Name of the account reference table.
ACCOUNTS_TABLE: Final = "accounts"

#: Name of the event journal table.
EVENTS_TABLE: Final = "events"

#: Timestamp resolutions pandas supports, mirroring ``features.datetime_resolution``.
DatetimeResolution = Literal["s", "ms", "us", "ns"]


class ContractType(StrEnum):
    """Billing rhythm of a contract, column ``accounts.type_contrat``."""

    MENSUEL = "mensuel"
    ANNUEL = "annuel"
    PLURIANNUEL = "pluriannuel"


class Segment(StrEnum):
    """Size segment of an account, column ``accounts.segment``."""

    TPE = "TPE"
    PME = "PME"
    ETI = "ETI"
    GRAND_COMPTE = "GrandCompte"


class AcquisitionChannel(StrEnum):
    """Channel the account was won through, column ``accounts.canal_acquisition``."""

    DIRECT = "direct"
    PARTENAIRE = "partenaire"
    INBOUND = "inbound"
    MARKETPLACE = "marketplace"


class EventType(StrEnum):
    """Closed nomenclature of ``events.event_type``.

    No source may introduce a value outside this enumeration. Adding a type is a
    change of the contract and is made in ``docs/data-contract.md`` first, never
    inside an adapter.

    No source fills the nomenclature entirely either. It is the union of what the
    planned sources can produce: KKBox has neither support nor sales contact, a
    company dataset would have no completion rate. A missing family simply yields
    fewer features, it is never an error.
    """

    CONNEXION = "connexion"
    USAGE_MODULE_CLE = "usage_module_cle"
    TAUX_COMPLETION = "taux_completion"
    DESACTIVATION_MODULE = "desactivation_module"
    TICKET_SUPPORT_OUVERT = "ticket_support_ouvert"
    TICKET_SUPPORT_RESOLU = "ticket_support_resolu"
    FACTURE_EMISE = "facture_emise"
    FACTURE_PAYEE = "facture_payee"
    ECHEC_PRELEVEMENT = "echec_prelevement"
    ANNULATION_ABONNEMENT = "annulation_abonnement"
    DESACTIVATION_RENOUVELLEMENT = "desactivation_renouvellement"
    CONTACT_COMMERCIAL = "contact_commercial"


#: Business family of every event type, as declared in the nomenclature table.
#: It is the prefix the business labels carry, for example ``[PRODUCT]``.
EVENT_FAMILIES: Final[dict[EventType, FeatureSource]] = {
    EventType.CONNEXION: FeatureSource.PRODUCT,
    EventType.USAGE_MODULE_CLE: FeatureSource.PRODUCT,
    EventType.TAUX_COMPLETION: FeatureSource.PRODUCT,
    EventType.DESACTIVATION_MODULE: FeatureSource.PRODUCT,
    EventType.TICKET_SUPPORT_OUVERT: FeatureSource.SUPPORT,
    EventType.TICKET_SUPPORT_RESOLU: FeatureSource.SUPPORT,
    EventType.FACTURE_EMISE: FeatureSource.FINANCE,
    EventType.FACTURE_PAYEE: FeatureSource.FINANCE,
    EventType.ECHEC_PRELEVEMENT: FeatureSource.FINANCE,
    EventType.ANNULATION_ABONNEMENT: FeatureSource.FINANCE,
    EventType.DESACTIVATION_RENOUVELLEMENT: FeatureSource.FINANCE,
    EventType.CONTACT_COMMERCIAL: FeatureSource.COMMERCIAL,
}


class ColumnRequirement(StrEnum):
    """Tells whether the column itself may be absent from a source."""

    CORE = "core"
    OPTIONAL = "optional"


class ColumnKind(StrEnum):
    """Family of pandas dtype a contract column maps to."""

    STRING = "string"
    TIMESTAMP = "timestamp"
    DECIMAL = "decimal"
    INTEGER = "integer"


@dataclass(frozen=True, slots=True)
class ColumnContract:
    """Contract metadata attached to a field of a record model.

    Attributes:
        kind: family of pandas dtype the column maps to.
        requirement: whether the column may be missing from a conformant source.
        nullable: whether a value inside the column may be missing.
    """

    kind: ColumnKind
    requirement: ColumnRequirement = ColumnRequirement.CORE
    nullable: bool = False


class _RecordModel(BaseModel):
    """Base of the record models, which refuse unknown keys and mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AccountRecord(_RecordModel):
    """One line of ``accounts``, the account reference table.

    Instantiating this model is meaningful for a handful of rows, in a test or a
    fixture. It is never used to walk a real dataset, see the module docstring.
    """

    client_id: Annotated[str, ColumnContract(ColumnKind.STRING), Field(min_length=1)]
    date_debut_contrat: Annotated[AwareDatetime, ColumnContract(ColumnKind.TIMESTAMP)]
    date_resiliation: Annotated[
        AwareDatetime | None,
        ColumnContract(ColumnKind.TIMESTAMP, nullable=True),
    ] = None
    type_contrat: Annotated[ContractType, ColumnContract(ColumnKind.STRING)]
    mrr: Annotated[float, ColumnContract(ColumnKind.DECIMAL), Field(ge=0.0)]
    segment: Annotated[Segment, ColumnContract(ColumnKind.STRING)]
    canal_acquisition: Annotated[AcquisitionChannel, ColumnContract(ColumnKind.STRING)]
    nb_licences: Annotated[
        Annotated[int, Field(gt=0)] | None,
        ColumnContract(ColumnKind.INTEGER, ColumnRequirement.OPTIONAL),
    ] = None


class EventRecord(_RecordModel):
    """One line of ``events``, the journal of dated events."""

    client_id: Annotated[str, ColumnContract(ColumnKind.STRING), Field(min_length=1)]
    event_ts: Annotated[AwareDatetime, ColumnContract(ColumnKind.TIMESTAMP)]
    event_type: Annotated[EventType, ColumnContract(ColumnKind.STRING)]
    event_value: Annotated[
        float | None,
        ColumnContract(ColumnKind.DECIMAL, nullable=True),
    ] = None


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Contract of a single column, derived from a field of a record model.

    Attributes:
        name: name of the column in the frame.
        kind: family of pandas dtype.
        requirement: whether the column may be absent from a source.
        nullable: whether a value may be missing.
        categories: closed set of accepted values, or ``None`` when the column is
            free. It is derived from the enumeration used in the record model, so
            the nomenclature is declared once.
    """

    name: str
    kind: ColumnKind
    requirement: ColumnRequirement
    nullable: bool
    categories: tuple[str, ...] | None

    @property
    def is_core(self) -> bool:
        """Whether the column must be present in a conformant source."""
        return self.requirement is ColumnRequirement.CORE

    def pandas_dtype(self, resolution: DatetimeResolution) -> str:
        """Return the pandas dtype string the column must carry.

        Args:
            resolution: timestamp resolution, from ``features.datetime_resolution``.

        Returns:
            A dtype string accepted by :meth:`pandas.Series.astype`.
        """
        match self.kind:
            case ColumnKind.TIMESTAMP:
                return f"datetime64[{resolution}, UTC]"
            case ColumnKind.DECIMAL:
                return "float64"
            case ColumnKind.INTEGER:
                return "int64"
            case ColumnKind.STRING:
                return "str"


def _strip_annotated(annotation: Any) -> Any:
    """Return the underlying type of a possibly ``Annotated`` annotation."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _unwrap_optional(annotation: Any) -> Any:
    """Return the single non ``None`` member of an optional annotation."""
    annotation = _strip_annotated(annotation)
    if get_origin(annotation) in (Union, types.UnionType):
        members = [
            _strip_annotated(member) for member in get_args(annotation) if member is not type(None)
        ]
        if len(members) == 1:
            return members[0]
    return annotation


def _categories_of(annotation: Any) -> tuple[str, ...] | None:
    """Return the closed value set of an annotation, when it is an enumeration."""
    inner = _unwrap_optional(annotation)
    if isinstance(inner, type) and issubclass(inner, StrEnum):
        return tuple(member.value for member in inner)
    return None


@dataclass(frozen=True, slots=True)
class TableSchema:
    """Contract of one input table.

    Attributes:
        name: name of the table, ``accounts`` or ``events``.
        record_model: the Pydantic model the specifications were derived from.
        columns: the column contracts, in the order of the data contract.
    """

    name: str
    record_model: type[BaseModel]
    columns: tuple[ColumnSpec, ...]

    @classmethod
    def from_record_model(cls, name: str, model: type[BaseModel]) -> TableSchema:
        """Build the schema of a table from its record model.

        Args:
            name: name of the table.
            model: record model carrying the :class:`ColumnContract` metadata.

        Returns:
            The table schema.

        Raises:
            TypeError: if a field of the model carries no contract metadata. That
                would leave a column outside the contract, which is never silent.
        """
        specs: list[ColumnSpec] = []
        for field_name, field in model.model_fields.items():
            contracts = [item for item in field.metadata if isinstance(item, ColumnContract)]
            if not contracts:
                message = (
                    f"field '{field_name}' of {model.__name__} carries no ColumnContract "
                    f"metadata, so its place in the data contract is undeclared"
                )
                raise TypeError(message)
            contract = contracts[0]
            specs.append(
                ColumnSpec(
                    name=field_name,
                    kind=contract.kind,
                    requirement=contract.requirement,
                    nullable=contract.nullable,
                    categories=_categories_of(field.annotation),
                )
            )
        return cls(name=name, record_model=model, columns=tuple(specs))

    @property
    def column_names(self) -> tuple[str, ...]:
        """Names of every declared column, core and optional."""
        return tuple(spec.name for spec in self.columns)

    @property
    def core_column_names(self) -> tuple[str, ...]:
        """Names of the mandatory columns."""
        return tuple(spec.name for spec in self.columns if spec.is_core)

    @property
    def optional_column_names(self) -> tuple[str, ...]:
        """Names of the columns a conformant source may omit."""
        return tuple(spec.name for spec in self.columns if not spec.is_core)

    @property
    def timestamp_columns(self) -> tuple[ColumnSpec, ...]:
        """Columns whose resolution and timezone are normalised at ingestion."""
        return tuple(spec for spec in self.columns if spec.kind is ColumnKind.TIMESTAMP)

    def column(self, name: str) -> ColumnSpec:
        """Return the contract of one column.

        Args:
            name: name of the column.

        Returns:
            The column contract.

        Raises:
            KeyError: if the column is not part of the contract.
        """
        for spec in self.columns:
            if spec.name == name:
                return spec
        message = f"column '{name}' is not declared in the '{self.name}' contract"
        raise KeyError(message)

    def missing_core_columns(self, present: Iterable[str]) -> tuple[str, ...]:
        """Return the mandatory columns absent from ``present``, in contract order."""
        available = set(present)
        return tuple(name for name in self.core_column_names if name not in available)

    def declared_columns(self, present: Iterable[str]) -> tuple[str, ...]:
        """Return the declared columns found in ``present``, in contract order."""
        available = set(present)
        return tuple(name for name in self.column_names if name in available)

    def empty_frame(self, resolution: DatetimeResolution) -> pd.DataFrame:
        """Return an empty frame carrying every declared column and its dtype.

        Useful to exercise the empty dataset path without special casing it.

        Args:
            resolution: timestamp resolution, from ``features.datetime_resolution``.

        Returns:
            An empty frame with the contract columns and dtypes.
        """
        return pd.DataFrame(
            {spec.name: pd.Series([], dtype=spec.pandas_dtype(resolution)) for spec in self.columns}
        )


#: Contract of the account reference table, section 1 of the data contract.
ACCOUNTS_SCHEMA: Final = TableSchema.from_record_model(ACCOUNTS_TABLE, AccountRecord)

#: Contract of the event journal, section 2 of the data contract.
EVENTS_SCHEMA: Final = TableSchema.from_record_model(EVENTS_TABLE, EventRecord)

#: Every declared table, keyed by name.
TABLE_SCHEMAS: Final[dict[str, TableSchema]] = {
    ACCOUNTS_SCHEMA.name: ACCOUNTS_SCHEMA,
    EVENTS_SCHEMA.name: EVENTS_SCHEMA,
}


@dataclass(frozen=True, slots=True)
class Dataset:
    """The pair of contract tables, whatever the origin of the data.

    Attributes:
        accounts: the account reference table.
        events: the journal of dated events.
    """

    accounts: pd.DataFrame
    events: pd.DataFrame
