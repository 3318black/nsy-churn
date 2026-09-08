"""Tests of the KKBox adapter.

The cases are built by hand rather than read from the raw extracts: those weigh
several gigabytes, are absent from the CI runner, and are not redistributable.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from churn.data.kkbox import (
    MAX_PLAUSIBLE_EXPIRY,
    REJECTED_COLUMNS,
    KkboxRawPaths,
    build_accounts,
    build_events,
    load_transactions,
    read_in_chunks,
    sample_account_ids,
)
from churn.data.schemas import Dataset, EventType
from churn.data.target import LabelWindow
from churn.data.validate import validate_dataset

MARCH_2017 = [LabelWindow.for_month(2017, 3)]


def _transactions() -> pd.DataFrame:
    """Return a small raw transaction table."""
    return pd.DataFrame(
        {
            "msno": ["A", "A", "B", "B"],
            "payment_method_id": [41, 41, 38, 38],
            "payment_plan_days": [30, 30, 410, 410],
            "plan_list_price": [149, 149, 1788, 1788],
            "actual_amount_paid": [149, 100, 1788, 1788],
            "transaction_date": [20170210, 20170315, 20170105, 20170220],
            "membership_expire_date": [20170312, 20170415, 20180220, 20190305],
            "is_cancel": [0, 0, 0, 1],
            "is_auto_renew": [1, 1, 0, 0],
        }
    )


def _members() -> pd.DataFrame:
    """Return a small raw account reference."""
    return pd.DataFrame(
        {
            "msno": ["A", "B", "C"],
            "city": [1, 13, 5],
            "registered_via": [7, 9, 3],
            "registration_init_time": [20150301, 20160715, 20140101],
        }
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> Path:
    """Write a frame as CSV and return the path."""
    frame.to_csv(path, index=False)
    return path


def test_paths_are_resolved_whatever_their_depth(tmp_path: Path) -> None:
    """The archives do not share one internal layout, so paths are searched."""
    nested = tmp_path / "data" / "churn_comp_refresh"
    nested.mkdir(parents=True)
    for name in ("members_v3.csv", "transactions.csv"):
        (tmp_path / name).write_text("msno\n", encoding="utf-8")
    for name in ("transactions_v2.csv", "train_v2.csv"):
        (nested / name).write_text("msno\n", encoding="utf-8")

    paths = KkboxRawPaths.discover(tmp_path)
    assert paths.members.parent == tmp_path
    assert paths.transactions_recent.parent == nested
    assert paths.user_logs_history is None


def test_a_missing_mandatory_extract_fails_explicitly(tmp_path: Path) -> None:
    """A missing mandatory file is named, never treated as empty."""
    with pytest.raises(FileNotFoundError, match=r"members_v3\.csv"):
        KkboxRawPaths.discover(tmp_path)


def test_sample_is_drawn_from_the_transactions(tmp_path: Path) -> None:
    """The reference holds 6.77 million accounts against 2.36 million in the
    transactions, so drawing from the reference would yield accounts with no
    computable target."""
    path = _write_csv(tmp_path / "tx.csv", pd.DataFrame({"msno": list("ABCDEFGH")}))
    drawn = sample_account_ids([path], sample_size=4, seed=1)
    assert len(drawn) == 4
    assert drawn <= set("ABCDEFGH")


def test_sampling_is_reproducible(tmp_path: Path) -> None:
    """Two runs with the same seed draw the same accounts."""
    path = _write_csv(tmp_path / "tx.csv", pd.DataFrame({"msno": [f"C{i}" for i in range(50)]}))
    assert sample_account_ids([path], 10, seed=7) == sample_account_ids([path], 10, seed=7)


def test_sampling_returns_everything_when_the_population_is_small(tmp_path: Path) -> None:
    """Asking for more accounts than exist yields the whole population."""
    path = _write_csv(tmp_path / "tx.csv", pd.DataFrame({"msno": list("ABC")}))
    assert sample_account_ids([path], 99, seed=1) == set("ABC")


def test_chunked_reading_filters_on_the_sample(tmp_path: Path) -> None:
    """The full listening log weighs 30.5 GB, it is never read in one go."""
    frame = pd.DataFrame({"msno": list("ABCDEF"), "date": range(6)})
    path = _write_csv(tmp_path / "logs.csv", frame)
    chunks = list(read_in_chunks(path, ["msno", "date"], account_ids={"B", "E"}, chunk_size=2))
    assert len(chunks) == 3
    assert set(pd.concat(chunks)["msno"]) == {"B", "E"}


def test_absurd_expiry_dates_are_neutralised(tmp_path: Path) -> None:
    """The raw data reaches 20361015, which would keep accounts active forever."""
    frame = _transactions()
    frame.loc[len(frame)] = {
        **dict.fromkeys(frame.columns, 0),
        "msno": "Z",
        "transaction_date": 20170101,
        "membership_expire_date": 20361015,
    }
    history = _write_csv(tmp_path / "transactions.csv", frame)
    recent = _write_csv(tmp_path / "transactions_v2.csv", frame.head(0))
    (tmp_path / "members_v3.csv").write_text("msno\n", encoding="utf-8")

    paths = KkboxRawPaths.discover(tmp_path)
    loaded = load_transactions(paths)
    assert (loaded["membership_expire_date"] < MAX_PLAUSIBLE_EXPIRY).all()
    assert "Z" not in set(loaded["msno"])
    assert history.exists() and recent.exists()


def test_rejected_columns_leave_a_trace(caplog: pytest.LogCaptureFixture) -> None:
    """Not loading a column is precisely how it gets dropped unnoticed.

    The rejection of ``bd``, whose values run from -7168 to 2016, is a decision
    and has to stay visible in the log.
    """
    with caplog.at_level(logging.WARNING, logger="churn.data.kkbox"):
        build_accounts(_members(), _transactions(), MARCH_2017)
    rejected = {record.column for record in caplog.records if hasattr(record, "column")}
    assert set(REJECTED_COLUMNS) <= rejected


def test_accounts_keep_only_the_accounts_that_have_transactions() -> None:
    """An account absent from the transactions has no computable target."""
    accounts = build_accounts(_members(), _transactions(), MARCH_2017)
    assert set(accounts["client_id"]) == {"A", "B"}


def test_monthly_revenue_is_brought_back_to_thirty_days() -> None:
    """A 410 day plan at 1788 is not a monthly revenue of 1788."""
    accounts = build_accounts(_members(), _transactions(), MARCH_2017).set_index("client_id")
    assert accounts.loc["A", "mrr"] == pytest.approx(149.0)
    assert accounts.loc["B", "mrr"] == pytest.approx(1788 / 410 * 30, rel=1e-3)


def test_contract_type_follows_the_plan_length() -> None:
    """The billing rhythm is derived from the plan, not invented."""
    accounts = build_accounts(_members(), _transactions(), MARCH_2017).set_index("client_id")
    assert accounts.loc["A", "type_contrat"] == "mensuel"
    assert accounts.loc["B", "type_contrat"] == "annuel"


def test_termination_comes_from_the_rebuilt_label() -> None:
    """The reference table and the training grid rest on one single rule.

    Account A expires on 2017-03-12 and renews on 2017-03-15, so it stays. It
    must not carry a termination date.
    """
    accounts = build_accounts(_members(), _transactions(), MARCH_2017).set_index("client_id")
    assert pd.isna(accounts.loc["A", "date_resiliation"])


def test_events_carry_the_families_the_source_can_produce() -> None:
    """KKBox has no support and no sales contact, which is not an error."""
    accounts = build_accounts(_members(), _transactions(), MARCH_2017)
    events = build_events(_transactions(), accounts)
    produced = set(events["event_type"])
    assert EventType.FACTURE_EMISE.value in produced
    assert EventType.ECHEC_PRELEVEMENT.value in produced
    assert EventType.TICKET_SUPPORT_OUVERT.value not in produced


def test_a_payment_shortfall_becomes_a_failed_debit() -> None:
    """Paying 100 against a listed 149 is a shortfall of 49."""
    accounts = build_accounts(_members(), _transactions(), MARCH_2017)
    events = build_events(_transactions(), accounts)
    failed = events.loc[events["event_type"] == EventType.ECHEC_PRELEVEMENT.value]
    assert len(failed) == 1
    assert failed.iloc[0]["event_value"] == pytest.approx(49.0)


def test_events_outside_the_contract_window_are_dropped() -> None:
    """The window comes from the reference table the adapter has just built."""
    transactions = _transactions()
    transactions.loc[len(transactions)] = {
        "msno": "A",
        "payment_method_id": 41,
        "payment_plan_days": 30,
        "plan_list_price": 149,
        "actual_amount_paid": 149,
        "transaction_date": 20100101,
        "membership_expire_date": 20100201,
        "is_cancel": 0,
        "is_auto_renew": 1,
    }
    accounts = build_accounts(_members(), transactions, MARCH_2017)
    events = build_events(transactions, accounts)
    started = accounts.set_index("client_id").loc["A", "date_debut_contrat"]
    assert (events.loc[events["client_id"] == "A", "event_ts"] >= started).all()


def test_the_projected_dataset_conforms_to_the_contract() -> None:
    """Criterion 6 of lot 2: no relaxation of the contract anywhere."""
    accounts = build_accounts(_members(), _transactions(), MARCH_2017)
    events = build_events(_transactions(), accounts)
    report = validate_dataset(Dataset(accounts, events), resolution="us")
    assert report.is_valid, report.render()
