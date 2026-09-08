"""Tests of the churn label reconstruction.

The cases are built by hand, so the expected answer comes from the rule stated in
``WSDMChurnLabeller.scala`` and not from what the code happens to produce.
"""

from __future__ import annotations

import pandas as pd

from churn.data.target import LabelWindow, label_window, order_transactions

#: Reference window used throughout: history of February, expiries of March.
MARCH_2017 = LabelWindow.for_month(2017, 3)


def _transaction(
    msno: str,
    transaction_date: int,
    membership_expire_date: int,
    is_cancel: int = 0,
    plan: int = 30,
    price: int = 149,
    method: int = 41,
) -> dict[str, object]:
    """Return one raw transaction row."""
    return {
        "msno": msno,
        "transaction_date": transaction_date,
        "membership_expire_date": membership_expire_date,
        "is_cancel": is_cancel,
        "payment_plan_days": plan,
        "plan_list_price": price,
        "payment_method_id": method,
    }


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Return the transactions as a frame."""
    return pd.DataFrame(rows)


def test_window_takes_the_previous_month_as_history() -> None:
    """The reference history is one month, not the whole past."""
    assert MARCH_2017.history_start == 20170201
    assert MARCH_2017.history_cutoff == 20170228
    assert MARCH_2017.expiry_start == 20170301
    assert MARCH_2017.expiry_end == 20170331


def test_january_window_spans_the_year_boundary() -> None:
    """The previous month of January is December of the year before."""
    window = LabelWindow.for_month(2017, 1)
    assert window.history_start == 20161201
    assert window.history_cutoff == 20161231


def test_a_prompt_renewal_is_not_a_churn() -> None:
    """A renewal inside the thirty day window keeps the account."""
    frame = _frame(
        [
            _transaction("A", 20170210, 20170312),
            _transaction("A", 20170315, 20170415),
        ]
    )
    result = label_window(frame, MARCH_2017).set_index("msno")
    assert result.loc["A", "renewal_gap"] == 3
    assert not result.loc["A", "is_churn"]


def test_a_late_renewal_is_a_churn() -> None:
    """Beyond thirty days the account has churned, even though it came back."""
    frame = _frame(
        [
            _transaction("A", 20170210, 20170312),
            _transaction("A", 20170420, 20170520),
        ]
    )
    result = label_window(frame, MARCH_2017).set_index("msno")
    assert result.loc["A", "renewal_gap"] == 39
    assert result.loc["A", "is_churn"]


def test_no_transaction_after_the_cutoff_is_a_churn() -> None:
    """No activity at all, so no gap to compute and no renewal either."""
    frame = _frame([_transaction("A", 20170210, 20170312)])
    result = label_window(frame, MARCH_2017).set_index("msno")
    assert pd.isna(result.loc["A", "renewal_gap"])
    assert result.loc["A", "is_churn"]


def test_an_early_renewal_yields_a_negative_gap_and_no_churn() -> None:
    """Renewing before the expiry is common and must not count as a churn."""
    frame = _frame(
        [
            _transaction("A", 20170210, 20170312),
            _transaction("A", 20170305, 20170411),
        ]
    )
    result = label_window(frame, MARCH_2017).set_index("msno")
    assert result.loc["A", "renewal_gap"] == -7
    assert not result.loc["A", "is_churn"]


def test_a_cancellation_brings_the_expiry_forward() -> None:
    """The cancellation shortens the subscription, so the same renewal date
    lands further from the expiry and turns a retention into a churn."""
    without = _frame(
        [
            _transaction("A", 20170210, 20170330),
            _transaction("A", 20170425, 20170525),
        ]
    )
    with_cancel = _frame(
        [
            _transaction("A", 20170210, 20170330),
            _transaction("A", 20170301, 20170305, is_cancel=1),
            _transaction("A", 20170425, 20170525),
        ]
    )
    kept = label_window(without, MARCH_2017).set_index("msno")
    cancelled = label_window(with_cancel, MARCH_2017).set_index("msno")

    assert kept.loc["A", "renewal_gap"] == 26
    assert not kept.loc["A", "is_churn"]
    assert cancelled.loc["A", "renewal_gap"] == 51
    assert cancelled.loc["A", "is_churn"]


def test_a_cancellation_never_pushes_the_expiry_back() -> None:
    """Only a cancellation landing before the expiry in force counts."""
    frame = _frame(
        [
            _transaction("A", 20170210, 20170310),
            _transaction("A", 20170301, 20170520, is_cancel=1),
            _transaction("A", 20170320, 20170420),
        ]
    )
    result = label_window(frame, MARCH_2017).set_index("msno")
    assert result.loc["A", "renewal_gap"] == 10


def test_an_expiry_outside_the_month_is_not_a_candidate() -> None:
    """An account whose subscription runs further is not labelled at all."""
    frame = _frame(
        [
            _transaction("A", 20170210, 20170615),
            _transaction("B", 20170210, 20170315),
        ]
    )
    result = label_window(frame, MARCH_2017)
    assert set(result["msno"]) == {"B"}


def test_the_expiry_in_force_comes_from_the_reference_month_only() -> None:
    """A transaction before the reference month does not set the expiry."""
    frame = _frame(
        [
            _transaction("A", 20161115, 20170320),
            _transaction("A", 20170205, 20170610),
        ]
    )
    # The February transaction sets the expiry to June, so A is not a candidate.
    assert label_window(frame, MARCH_2017).empty


def test_same_day_subscription_precedes_cancellation() -> None:
    """The ordering rule puts the subscription first, so the cancellation of the
    same day is what remains in force."""
    frame = _frame(
        [
            _transaction("A", 20170220, 20170415),
            _transaction("A", 20170220, 20170310, is_cancel=1),
        ]
    )
    ordered = order_transactions(frame)
    assert list(ordered["is_cancel"]) == [0, 1]
    result = label_window(frame, MARCH_2017).set_index("msno")
    assert result.loc["A", "is_churn"]


def test_consecutive_renewals_of_a_day_keep_extending() -> None:
    """Among renewals of one day, the later expiry stays in force."""
    frame = _frame(
        [
            _transaction("A", 20170220, 20170320),
            _transaction("A", 20170220, 20170310),
        ]
    )
    ordered = order_transactions(frame)
    assert list(ordered["membership_expire_date"]) == [20170310, 20170320]


def test_consecutive_cancellations_of_a_day_keep_shortening() -> None:
    """Among cancellations of one day, the earlier expiry stays in force."""
    frame = _frame(
        [
            _transaction("A", 20170220, 20170305, is_cancel=1),
            _transaction("A", 20170220, 20170320, is_cancel=1),
        ]
    )
    ordered = order_transactions(frame)
    assert list(ordered["membership_expire_date"]) == [20170320, 20170305]


def test_an_empty_history_yields_no_label() -> None:
    """No reference month means no candidate, and no crash either."""
    frame = _frame([_transaction("A", 20160101, 20160201)])
    assert label_window(frame, MARCH_2017).empty
