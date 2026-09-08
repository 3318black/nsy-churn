"""Reconstruction of the KKBox churn label from the raw transactions.

``train_v2.csv`` carries the label for one month only, so it cannot feed a multi
date observation grid, which is the base of the whole protocol. The label is
therefore rebuilt here, and the rebuild is checked against the official file.

**The rule is not guessable and was not guessed.** It is transcribed from
``WSDMChurnLabeller.scala``, shipped with the competition. Five points of it would
have been wrong under any reasonable assumption.

1. The reference history is **one month**, not the whole past. Only the
   transactions of that month set the current expiry.
2. Candidates are the accounts whose expiry falls in the **following** month.
   An account whose subscription runs further is not a candidate at all.
3. The gap is measured between the expiry and the **transaction date** of the
   renewal, never between two expiries.
4. A cancellation may **bring the expiry forward**, and consecutive
   cancellations keep bringing it forward.
5. Transactions of a single day are ordered by a precise rule: descending plan
   signature, then subscription before cancellation, then expiry ascending for
   renewals and descending for cancellations.

An account with no transaction at all after the cutoff is a churner, without any
gap being computed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "OFFICIAL_RENEWAL_WINDOW_DAYS",
    "TRANSACTION_ORDER_COLUMNS",
    "LabelWindow",
    "label_window",
    "order_transactions",
]

#: Days a renewal may take before the account counts as churned.
OFFICIAL_RENEWAL_WINDOW_DAYS = 30

#: Columns the ordering rule needs, beyond the account identifier.
TRANSACTION_ORDER_COLUMNS = (
    "transaction_date",
    "membership_expire_date",
    "is_cancel",
    "payment_method_id",
    "payment_plan_days",
    "plan_list_price",
)


@dataclass(frozen=True, slots=True)
class LabelWindow:
    """One labelling period, as the official labeller defines it.

    Attributes:
        history_start: first day of the reference month, as ``AAAAMMJJ``.
        history_cutoff: last day of the reference month, as ``AAAAMMJJ``.
        expiry_start: first day of the candidate expiry month.
        expiry_end: last day of the candidate expiry month.
    """

    history_start: int
    history_cutoff: int
    expiry_start: int
    expiry_end: int

    @classmethod
    def for_month(cls, year: int, month: int) -> LabelWindow:
        """Build the window whose candidates expire during the given month.

        The reference history is the month before, exactly as the official
        labeller does.

        Args:
            year: year of the expiry month.
            month: month the candidate subscriptions expire in.

        Returns:
            The labelling window.
        """
        expiry = pd.Period(year=year, month=month, freq="M")
        history = expiry - 1
        return cls(
            history_start=int(history.start_time.strftime("%Y%m%d")),
            history_cutoff=int(history.end_time.strftime("%Y%m%d")),
            expiry_start=int(expiry.start_time.strftime("%Y%m%d")),
            expiry_end=int(expiry.end_time.strftime("%Y%m%d")),
        )


def order_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return the transactions in the order the official labeller applies.

    Within one account and one day, the rule is: descending plan signature, then
    subscription before cancellation, then expiry ascending for renewals and
    descending for cancellations. The two expiry directions are folded into a
    single ascending key by negating the cancellations, so the whole ordering is
    one vectorised sort rather than a comparator walking the rows.

    Args:
        transactions: raw transactions, carrying at least the ordering columns.

    Returns:
        A new frame, ordered per account.
    """
    ordered = transactions.copy()
    ordered["_signature"] = (
        ordered["plan_list_price"].astype(str)
        + ordered["payment_plan_days"].astype(str)
        + ordered["payment_method_id"].astype(str)
    )
    # Renewals extend the expiry, cancellations bring it forward: negating the
    # cancelled ones turns both directions into a single ascending key.
    ordered["_expiry_key"] = np.where(
        ordered["is_cancel"] == 1,
        -ordered["membership_expire_date"],
        ordered["membership_expire_date"],
    )
    return ordered.sort_values(
        ["msno", "transaction_date", "_signature", "is_cancel", "_expiry_key"],
        ascending=[True, True, False, True, True],
        kind="stable",
    )


def _current_expiry(history: pd.DataFrame) -> pd.Series:
    """Return the expiry in force at the cutoff, per account.

    It is the expiry of the last transaction of the reference month, in the
    official order. Taking the maximum expiry instead would ignore cancellations,
    which legitimately bring the date forward.
    """
    ordered = order_transactions(history)
    return ordered.groupby("msno", sort=False)["membership_expire_date"].last()


def _renewal_gap(future: pd.DataFrame, current_expiry: pd.Series) -> pd.Series:
    """Return the days between the expiry and the first renewal, per account.

    Walks the transactions that follow the cutoff in the official order. A
    cancellation that lands before the expiry in force brings it forward. The
    first subscription stops the walk and fixes the gap.

    The sequential walk of the original implementation is folded into three
    vectorised steps: rank the transactions, find the first subscription, then
    take the running minimum of the cancellations that precede it.

    Args:
        future: transactions posterior to the cutoff, for candidate accounts.
        current_expiry: expiry in force at the cutoff, indexed by account.

    Returns:
        The gap in days, indexed by account. An account without any subscription
        after the cutoff is absent from the result.
    """
    ordered = order_transactions(future)
    ordered["_rank"] = ordered.groupby("msno", sort=False).cumcount()

    subscriptions = ordered.loc[ordered["is_cancel"] == 0]
    # ``head(1)`` rather than ``first()``: the latter takes the first non null
    # value of each column independently, so a single missing cell would mix two
    # transactions into one phantom row.
    first_subscription = subscriptions.groupby("msno", sort=False).head(1).set_index("msno")
    if first_subscription.empty:
        return pd.Series(dtype="int64")

    # Cancellations strictly before the first subscription may bring the expiry
    # forward. Their running minimum is enough, the walk only ever lowers it.
    cancellations = ordered.loc[ordered["is_cancel"] == 1]
    cancellations = cancellations.join(first_subscription["_rank"].rename("_sub_rank"), on="msno")
    before = cancellations.loc[cancellations["_rank"] < cancellations["_sub_rank"]]
    earliest_cancel = before.groupby("msno", sort=False)["membership_expire_date"].min()

    expiry = current_expiry.reindex(first_subscription.index)
    brought_forward = earliest_cancel.reindex(first_subscription.index)
    adjusted = np.minimum(expiry, brought_forward.fillna(expiry))

    renewal_date = pd.to_datetime(
        first_subscription["transaction_date"].astype(int).astype(str), format="%Y%m%d"
    )
    expiry_date = pd.to_datetime(adjusted.astype(int).astype(str), format="%Y%m%d")
    return (renewal_date - expiry_date).dt.days


def label_window(
    transactions: pd.DataFrame,
    window: LabelWindow,
    renewal_window_days: int = OFFICIAL_RENEWAL_WINDOW_DAYS,
) -> pd.DataFrame:
    """Rebuild the churn label for one period.

    Args:
        transactions: raw transactions, with the columns of
            :data:`TRANSACTION_ORDER_COLUMNS` plus ``msno``.
        window: the labelling period.
        renewal_window_days: days a renewal may take before the account counts
            as churned.

    Returns:
        A frame with ``msno``, ``is_churn`` and ``renewal_gap``. Only the
        candidate accounts appear, that is those whose expiry in force falls
        inside the expiry month of the window.
    """
    history = transactions.loc[
        transactions["transaction_date"].between(window.history_start, window.history_cutoff)
    ]
    if history.empty:
        return pd.DataFrame(columns=["msno", "is_churn", "renewal_gap"])

    expiry = _current_expiry(history)
    candidates = expiry[expiry.between(window.expiry_start, window.expiry_end)]
    if candidates.empty:
        return pd.DataFrame(columns=["msno", "is_churn", "renewal_gap"])

    future = transactions.loc[
        (transactions["transaction_date"] > window.history_cutoff)
        & transactions["msno"].isin(candidates.index)
    ]
    gap = _renewal_gap(future, candidates)

    result = pd.DataFrame({"msno": candidates.index})
    result["renewal_gap"] = result["msno"].map(gap)
    # No subscription after the cutoff at all, so no renewal: the account churns
    # without any gap being computable.
    result["is_churn"] = (result["renewal_gap"].isna()) | (
        result["renewal_gap"] >= renewal_window_days
    )
    return result.reset_index(drop=True)
