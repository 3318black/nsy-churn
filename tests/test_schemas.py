"""Tests of the executable data contract."""

from __future__ import annotations

import pytest

from churn.config import FeatureSource
from churn.data.schemas import (
    ACCOUNTS_SCHEMA,
    EVENT_FAMILIES,
    EVENTS_SCHEMA,
    ColumnKind,
    ColumnRequirement,
    EventType,
)


def test_accounts_declares_the_contract_columns() -> None:
    """Section 1 of the data contract, column by column."""
    assert ACCOUNTS_SCHEMA.column_names == (
        "client_id",
        "date_debut_contrat",
        "date_resiliation",
        "type_contrat",
        "mrr",
        "segment",
        "canal_acquisition",
        "nb_licences",
    )


def test_events_declares_the_contract_columns() -> None:
    """Section 2 of the data contract, column by column."""
    assert EVENTS_SCHEMA.column_names == (
        "client_id",
        "event_ts",
        "event_type",
        "event_value",
    )


def test_nb_licences_is_the_only_optional_column() -> None:
    """A source that omits it stays conformant, see dataset-kkbox.md section 3."""
    assert ACCOUNTS_SCHEMA.optional_column_names == ("nb_licences",)
    assert EVENTS_SCHEMA.optional_column_names == ()
    assert ACCOUNTS_SCHEMA.column("nb_licences").requirement is ColumnRequirement.OPTIONAL


def test_nullable_is_distinct_from_optional() -> None:
    """A present column may hold a missing value, that is a different question.

    ``date_resiliation`` is mandatory as a column and null for an active account.
    """
    resiliation = ACCOUNTS_SCHEMA.column("date_resiliation")
    assert resiliation.is_core
    assert resiliation.nullable
    assert EVENTS_SCHEMA.column("event_value").nullable


def test_event_nomenclature_is_closed_and_complete() -> None:
    """The thirteen declared types, and a family for each of them."""
    assert len(EventType) == 12
    assert set(EVENT_FAMILIES) == set(EventType)
    assert set(EVENT_FAMILIES.values()) <= set(FeatureSource)


def test_event_type_column_carries_the_nomenclature() -> None:
    """The closed value set is derived from the enumeration, declared once."""
    categories = EVENTS_SCHEMA.column("event_type").categories
    assert categories is not None
    assert set(categories) == {member.value for member in EventType}


@pytest.mark.parametrize("resolution", ["us", "ns"])
def test_timestamp_dtype_follows_the_configured_resolution(resolution: str) -> None:
    """Mixing resolutions makes merge_asof fail, see data-contract.md 3.5."""
    spec = EVENTS_SCHEMA.column("event_ts")
    assert spec.kind is ColumnKind.TIMESTAMP
    assert spec.pandas_dtype(resolution) == f"datetime64[{resolution}, UTC]"  # type: ignore[arg-type]


def test_missing_core_columns_reports_in_contract_order() -> None:
    """The report follows the contract order, not the order of the frame."""
    present = ["mrr", "client_id"]
    assert ACCOUNTS_SCHEMA.missing_core_columns(present) == (
        "date_debut_contrat",
        "date_resiliation",
        "type_contrat",
        "segment",
        "canal_acquisition",
    )


def test_empty_frame_carries_every_column_and_dtype() -> None:
    """The empty dataset path needs no special casing downstream."""
    frame = ACCOUNTS_SCHEMA.empty_frame("us")
    assert list(frame.columns) == list(ACCOUNTS_SCHEMA.column_names)
    assert frame.empty
    assert str(frame["date_debut_contrat"].dtype) == "datetime64[us, UTC]"


def test_unknown_column_is_refused() -> None:
    """Asking for a column outside the contract is an error, never a default."""
    with pytest.raises(KeyError, match="not declared"):
        ACCOUNTS_SCHEMA.column("colonne_inventee")
