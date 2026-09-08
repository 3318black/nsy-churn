"""Tests of the contract validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from churn.data.schemas import Dataset
from churn.data.validate import ValidationError, validate_accounts, validate_dataset

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def _accounts() -> pd.DataFrame:
    """Return a small conformant account table."""
    return pd.DataFrame(
        {
            "client_id": ["C1", "C2"],
            "date_debut_contrat": pd.to_datetime(["2025-01-01", "2025-02-01"], utc=True).as_unit(
                "us"
            ),
            "date_resiliation": pd.to_datetime([None, "2025-08-01"], utc=True).as_unit("us"),
            "type_contrat": ["mensuel", "annuel"],
            "mrr": [100.0, 250.0],
            "segment": ["PME", "ETI"],
            "canal_acquisition": ["direct", "inbound"],
            "nb_licences": [5, 12],
        }
    )


def _events() -> pd.DataFrame:
    """Return a small conformant event journal."""
    return pd.DataFrame(
        {
            "client_id": ["C1", "C2"],
            "event_ts": pd.to_datetime(["2025-03-01", "2025-03-02"], utc=True).as_unit("us"),
            "event_type": ["connexion", "ticket_support_ouvert"],
            "event_value": [3.0, 2.0],
        }
    )


def test_a_conformant_dataset_passes() -> None:
    """The reference case, so a later failure means something."""
    report = validate_dataset(Dataset(_accounts(), _events()), now=NOW, resolution="us")
    assert report.is_valid, report.render()


def test_three_distinct_breaches_are_all_reported() -> None:
    """Criterion 2 of lot 1: three defects, three messages, in one run.

    Stopping at the first breach would force one run per defect, which is
    unworkable on a frame holding millions of rows.
    """
    events = _events()
    events.loc[len(events)] = {
        "client_id": "C_ORPHELIN",
        "event_ts": pd.Timestamp("2025-04-01", tz="UTC"),
        "event_type": "type_invente",
        "event_value": 1.0,
    }
    events["event_ts"] = events["event_ts"].dt.tz_localize(None)

    report = validate_dataset(Dataset(_accounts(), events), now=NOW)

    assert "client_id_exists_in_accounts" in report.invariants
    assert "event_type_in_nomenclature" in report.invariants
    assert "event_ts_timezone_aware" in report.invariants
    rendered = report.render()
    assert "C_ORPHELIN" in rendered
    assert "type_invente" not in rendered or "nomenclature" in rendered


def test_optional_column_may_be_absent() -> None:
    """Criterion 4 of lot 1: omitting nb_licences keeps the source conformant."""
    accounts = _accounts().drop(columns=["nb_licences"])
    report = validate_dataset(Dataset(accounts, _events()), now=NOW)
    assert report.is_valid, report.render()


def test_missing_core_column_is_a_breach() -> None:
    """A core column is another matter entirely."""
    accounts = _accounts().drop(columns=["mrr"])
    report = validate_accounts(accounts, now=NOW)
    assert report.invariants == ("core_columns_present",)
    assert "mrr" in report.render()


def test_duplicated_identifier_is_a_breach() -> None:
    """client_id is the primary key of the reference table."""
    accounts = pd.concat([_accounts(), _accounts().head(1)], ignore_index=True)
    report = validate_accounts(accounts, now=NOW)
    assert "client_id_unique" in report.invariants


def test_termination_must_follow_the_start_of_contract() -> None:
    """A termination on or before the start is impossible, not merely odd."""
    accounts = _accounts()
    accounts.loc[1, "date_resiliation"] = accounts.loc[1, "date_debut_contrat"]
    report = validate_accounts(accounts, now=NOW)
    assert "resiliation_after_debut" in report.invariants


def test_dates_in_the_future_are_refused() -> None:
    """The execution instant is injected, so the test stays deterministic."""
    accounts = _accounts()
    accounts.loc[0, "date_debut_contrat"] = pd.Timestamp("2030-01-01", tz="UTC")
    report = validate_accounts(accounts, now=NOW)
    assert "date_debut_contrat_not_in_future" in report.invariants


def test_negative_revenue_is_refused() -> None:
    """mrr is positive or zero, never negative."""
    accounts = _accounts()
    accounts.loc[0, "mrr"] = -1.0
    report = validate_accounts(accounts, now=NOW)
    assert "mrr_non_negative" in report.invariants


def test_event_outside_the_contract_window_is_a_breach() -> None:
    """An event before the start or after the termination has no meaning."""
    events = _events()
    events.loc[1, "event_ts"] = pd.Timestamp("2025-12-01", tz="UTC")
    report = validate_dataset(Dataset(_accounts(), events), now=NOW)
    assert "event_before_resiliation" in report.invariants


def test_resolution_mismatch_is_reported() -> None:
    """Mixing [us] and [ns] makes merge_asof fail later, see contract 3.5."""
    events = _events()
    events["event_ts"] = events["event_ts"].astype("datetime64[ns, UTC]")
    report = validate_dataset(Dataset(_accounts(), events), now=NOW, resolution="us")
    assert "event_ts_resolution" in report.invariants


def test_report_carries_a_sample_of_offending_identifiers() -> None:
    """A bare count is not actionable on a multi million row frame."""
    accounts = _accounts()
    accounts.loc[0, "mrr"] = -5.0
    report = validate_accounts(accounts, now=NOW)
    violation = report.violations[0]
    assert violation.count == 1
    assert violation.sample == ("C1",)


def test_raising_carries_the_full_report() -> None:
    """The caller inspects invariants rather than parsing a message."""
    accounts = _accounts()
    accounts.loc[0, "mrr"] = -5.0
    with pytest.raises(ValidationError) as caught:
        validate_accounts(accounts, now=NOW).raise_if_invalid()
    assert "mrr_non_negative" in caught.value.report.invariants
