"""What the account sheet shows besides the score: a profile and the actions to take.

Two rules, the same as everywhere in the interface.

Nothing after the scoring date
    The profile is built from the events strictly before the scoring date. A
    salesperson preparing a call on Monday must see what was known on Monday.
Nothing that misleads
    From the reference table, only the registration date is shown: it is a fixed
    fact of the past. The contract type describes the account at extraction time,
    decision D18, and on KKBox the segment and the acquisition channel are opaque
    codes. None of them is shown. The termination date, a fact of the future,
    obviously neither.

The suggested action of a factor comes from ``config/feature_mapping.yaml``, the
same static dictionary that names the factors. No text is generated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from churn.config import FeatureMappingEntry
from churn.data.schemas import EventType
from churn.interface.readers import account_history

__all__ = ["RECENT_ACTIVITY_DAYS", "AccountProfile", "account_profile", "suggested_actions"]

#: Days the recent activity of an account is counted over.
RECENT_ACTIVITY_DAYS = 30


@dataclass(frozen=True, slots=True)
class AccountProfile:
    """What was known about an account on the scoring date.

    Attributes:
        registered: registration date, when the reference table is available.
        tenure_days: days between registration and the scoring date.
        last_usage: date of the last usage event before the scoring date.
        days_since_usage: days between that last usage and the scoring date.
        active_days_recent: distinct days with usage over the last 30 days.
        last_payment: date of the last invoice before the scoring date.
        last_payment_amount: amount of that invoice.
        cancellations: subscription cancellations before the scoring date.
        auto_renew_disabled: times automatic renewal was found disabled.
    """

    registered: date | None
    tenure_days: int | None
    last_usage: date | None
    days_since_usage: int | None
    active_days_recent: int
    last_payment: date | None
    last_payment_amount: float | None
    cancellations: int
    auto_renew_disabled: int

    @property
    def is_empty(self) -> bool:
        """Whether nothing at all is known about the account."""
        return self.registered is None and self.last_usage is None and self.last_payment is None


def _registration(accounts_path: Path, client_id: str) -> date | None:
    """Return the registration date of one account, when the reference is on disk."""
    if not accounts_path.is_file():
        return None
    accounts = pd.read_parquet(
        accounts_path,
        columns=["client_id", "date_debut_contrat"],
        filters=[("client_id", "==", client_id)],
    )
    if accounts.empty:
        return None
    return pd.Timestamp(accounts["date_debut_contrat"].iloc[0]).date()


def account_profile(
    accounts_path: Path, events_path: Path, client_id: str, before: pd.Timestamp
) -> AccountProfile:
    """Build the profile of one account from what was known before a date.

    Args:
        accounts_path: the contract reference table of the source.
        events_path: the contract journal of the source.
        client_id: the account.
        before: timezone aware scoring date, excluded.

    Returns:
        The profile. Missing files yield an empty profile, never an error.
    """
    registered = _registration(accounts_path, client_id)
    history = account_history(events_path, client_id, before)
    kinds = history["event_type"]

    usage = history.loc[kinds == EventType.CONNEXION.value, "event_ts"]
    recent = usage.loc[usage >= before - pd.Timedelta(days=RECENT_ACTIVITY_DAYS)]
    last_usage = usage.max().date() if not usage.empty else None

    invoices = history.loc[kinds == EventType.FACTURE_EMISE.value]
    last_invoice = invoices.iloc[-1] if not invoices.empty else None

    scoring_day = before.date()
    return AccountProfile(
        registered=registered,
        tenure_days=(scoring_day - registered).days if registered else None,
        last_usage=last_usage,
        days_since_usage=(scoring_day - last_usage).days if last_usage else None,
        # An absent journal yields an untyped empty column, without a date accessor.
        active_days_recent=int(recent.dt.date.nunique()) if not recent.empty else 0,
        last_payment=last_invoice["event_ts"].date() if last_invoice is not None else None,
        last_payment_amount=(
            float(last_invoice["event_value"]) if last_invoice is not None else None
        ),
        cancellations=int((kinds == EventType.ANNULATION_ABONNEMENT.value).sum()),
        auto_renew_disabled=int((kinds == EventType.DESACTIVATION_RENOUVELLEMENT.value).sum()),
    )


def suggested_actions(mapping: Mapping[str, FeatureMappingEntry]) -> dict[str, str]:
    """Return the action to take for each factor label, as the export prints it.

    The label is rendered exactly as :func:`churn.models.explain.factor_labels`
    renders it, ``[SOURCE] label``, which a test checks. Factors without an
    action, the structural ones, are absent.

    Args:
        mapping: the business mapping.

    Returns:
        The suggested action, keyed by printed factor label.
    """
    return {
        f"[{entry.source.value}] {entry.label}": entry.action
        for entry in mapping.values()
        if entry.action.strip()
    }
