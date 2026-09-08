"""Projection of the raw KKBox extracts onto the data contract.

The contract never bends to a source. This module is the adapter that makes
KKBox conform, and it relaxes nothing: a breach surfaces through the validator
rather than being worked around here.

Four traps of this dataset are handled explicitly, each measured beforehand and
documented in ``docs/dataset-kkbox.md``.

Two generations of files
    The ``_v2`` files do not supersede the others, they complete them. 74.8% of
    ``transactions_v2.csv`` falls in March 2017, so loading it alone would shrink
    the history to a single month. Both are read and concatenated. The 1315
    overlapping rows are not duplicates: they are transactions the first file
    does not hold, so deduplication stays strictly exact.
Sampling population
    The reference holds 6.77 million accounts but only 2.36 million appear in the
    transactions. Drawing the sample from the reference would yield two thirds of
    accounts with no computable target. The sample is drawn from the transactions.
The ``bd`` column
    67% of its values fall outside a plausible age range, from -7168 to 2016. It
    is rejected with a trace in the log, never silently ignored.
Absurd expiry dates
    ``membership_expire_date`` reaches 20361015. Left alone, those accounts would
    stay active forever and rot the target.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from churn.data.schemas import (
    ACCOUNTS_SCHEMA,
    EVENTS_SCHEMA,
    AcquisitionChannel,
    ContractType,
    Dataset,
    DatetimeResolution,
    EventType,
    Segment,
)
from churn.data.target import LabelWindow, label_window, order_transactions

__all__ = [
    "KKBOX_DATE_FORMAT",
    "MAX_PLAUSIBLE_EXPIRY",
    "REJECTED_COLUMNS",
    "KkboxRawPaths",
    "build_accounts",
    "build_events",
    "load_transactions",
    "read_in_chunks",
    "sample_account_ids",
]

logger = logging.getLogger(__name__)

#: Raw dates are integers shaped as ``AAAAMMJJ``.
KKBOX_DATE_FORMAT = "%Y%m%d"

#: Any expiry beyond this bound is absurd and treated as missing. The raw data
#: reaches 20361015, which would keep the account active forever.
MAX_PLAUSIBLE_EXPIRY = 20180101

#: Columns deliberately dropped, with the reason kept next to the decision.
REJECTED_COLUMNS = {
    "bd": "67% of values outside a plausible age range, from -7168 to 2016",
    "gender": "not part of the contract and of no business use for the target",
}

#: Columns the transaction files carry and the pipeline needs.
_TRANSACTION_COLUMNS = [
    "msno",
    "payment_method_id",
    "payment_plan_days",
    "plan_list_price",
    "actual_amount_paid",
    "transaction_date",
    "membership_expire_date",
    "is_cancel",
    "is_auto_renew",
]

#: Columns the listening logs carry and the pipeline needs.
_LOG_COLUMNS = [
    "msno",
    "date",
    "num_25",
    "num_50",
    "num_75",
    "num_985",
    "num_100",
    "num_unq",
    "total_secs",
]

#: Plan length, in days, above which a contract stops being monthly.
MONTHLY_PLAN_MAX_DAYS = 45

#: Plan length, in days, above which a contract counts as yearly.
MULTIYEAR_PLAN_MAX_DAYS = 180

#: Days a monthly revenue is normalised on.
MONTHLY_BASIS_DAYS = 30


@dataclass(frozen=True, slots=True)
class KkboxRawPaths:
    """Where the raw extracts sit, after download and flattening.

    The archives do not share one internal layout: the ``_v2`` ones carry a
    ``data/churn_comp_refresh/`` prefix and the others do not. Paths are resolved
    by search rather than assumed, see ``dataset-kkbox.md`` section 2.2.

    Attributes:
        members: account reference.
        transactions_history: subscription history, first phase.
        transactions_recent: subscriptions, second phase.
        user_logs_history: listening logs, first phase, optional.
        user_logs_recent: listening logs, second phase, optional.
        official_labels: official churn label, used for the concordance check.
    """

    members: Path
    transactions_history: Path
    transactions_recent: Path
    user_logs_history: Path | None
    user_logs_recent: Path | None
    official_labels: Path | None

    @classmethod
    def discover(cls, raw_directory: Path) -> KkboxRawPaths:
        """Locate the extracts under ``raw_directory``, whatever their depth.

        Args:
            raw_directory: directory the archives were extracted into.

        Returns:
            The resolved paths. Optional files absent from disk are ``None``.

        Raises:
            FileNotFoundError: when a mandatory file is missing.
        """

        def find(name: str, *, required: bool) -> Path | None:
            matches = sorted(raw_directory.rglob(name))
            if matches:
                return matches[0]
            if required:
                message = f"missing mandatory extract '{name}' under {raw_directory}"
                raise FileNotFoundError(message)
            logger.warning("optional extract not found", extra={"file": name})
            return None

        members = find("members_v3.csv", required=True)
        history = find("transactions.csv", required=True)
        recent = find("transactions_v2.csv", required=True)
        assert members is not None and history is not None and recent is not None
        return cls(
            members=members,
            transactions_history=history,
            transactions_recent=recent,
            user_logs_history=find("user_logs.csv", required=False),
            user_logs_recent=find("user_logs_v2.csv", required=False),
            official_labels=find("train_v2.csv", required=False),
        )


def read_in_chunks(
    path: Path,
    columns: list[str],
    account_ids: set[str] | None = None,
    chunk_size: int = 1_000_000,
) -> Iterator[pd.DataFrame]:
    """Yield the rows of a CSV, filtered on an account sample.

    The full listening log weighs 30.5 GB once uncompressed, so it is never read
    in one go. Filtering inside the loop keeps only the sample in memory.

    Args:
        path: file to read.
        columns: columns to keep.
        account_ids: accounts to keep, or ``None`` for all of them.
        chunk_size: rows per chunk.

    Yields:
        The filtered chunks, in file order.
    """
    for chunk in pd.read_csv(path, usecols=columns, chunksize=chunk_size):
        yield chunk if account_ids is None else chunk[chunk["msno"].isin(account_ids)]


def sample_account_ids(
    transaction_paths: Iterable[Path],
    sample_size: int,
    seed: int,
    chunk_size: int = 1_000_000,
) -> set[str]:
    """Draw the account sample from the transactions, never from the reference.

    The reference holds 6.77 million accounts against 2.36 million in the
    transactions. Drawing from the reference would yield roughly two thirds of
    accounts with no transaction, hence no computable target and no financial
    feature.

    Args:
        transaction_paths: the transaction files.
        sample_size: number of accounts to draw.
        seed: seed of the draw, so two runs match.
        chunk_size: rows per chunk.

    Returns:
        The drawn identifiers.
    """
    known: set[str] = set()
    for path in transaction_paths:
        for chunk in pd.read_csv(path, usecols=["msno"], chunksize=chunk_size):
            known.update(chunk["msno"].unique())

    population = np.array(sorted(known))
    logger.info(
        "accounts available in the transactions",
        extra={"population": len(population), "requested": sample_size},
    )
    if len(population) <= sample_size:
        return set(population)
    rng = np.random.default_rng(seed)
    return set(rng.choice(population, size=sample_size, replace=False))


def load_transactions(
    paths: KkboxRawPaths,
    account_ids: set[str] | None = None,
    chunk_size: int = 1_000_000,
) -> pd.DataFrame:
    """Load and concatenate both generations of transaction files.

    Deduplication is strictly exact. The 1315 rows the two files share in period
    are not duplicates: they are transactions the first file does not hold.

    Args:
        paths: resolved raw paths.
        account_ids: accounts to keep, or ``None`` for all of them.
        chunk_size: rows per chunk.

    Returns:
        The concatenated transactions.
    """
    frames = [
        chunk
        for path in (paths.transactions_history, paths.transactions_recent)
        for chunk in read_in_chunks(path, _TRANSACTION_COLUMNS, account_ids, chunk_size)
    ]
    transactions = pd.concat(frames, ignore_index=True).drop_duplicates()
    absurd = transactions["membership_expire_date"] >= MAX_PLAUSIBLE_EXPIRY
    if absurd.any():
        logger.warning(
            "absurd expiry dates neutralised",
            extra={"rows": int(absurd.sum()), "bound": MAX_PLAUSIBLE_EXPIRY},
        )
        transactions = transactions.loc[~absurd]
    return transactions


def _termination_dates(transactions: pd.DataFrame, months: list[LabelWindow]) -> pd.Series:
    """Return the termination date of each account, or ``NaT`` when still active.

    An account terminates at the expiry of the first month it is labelled a
    churner on. The label comes from :mod:`churn.data.target`, so the reference
    table and the training grid rest on one single rule.

    Args:
        transactions: the concatenated transactions.
        months: labelling windows, in chronological order.

    Returns:
        The termination timestamps, indexed by account.
    """
    terminated: dict[str, int] = {}
    for window in months:
        labelled = label_window(transactions, window)
        if labelled.empty:
            continue
        churners = labelled.loc[labelled["is_churn"], "msno"]
        expiry = _current_expiry_of(transactions, window)
        for account in churners:
            if account not in terminated:
                terminated[account] = int(expiry.get(account, window.expiry_end))
    if not terminated:
        return pd.Series(dtype="datetime64[us, UTC]")
    dates = pd.Series(terminated)
    return pd.to_datetime(dates.astype(str), format=KKBOX_DATE_FORMAT, utc=True).dt.as_unit("us")


def _current_expiry_of(transactions: pd.DataFrame, window: LabelWindow) -> pd.Series:
    """Return the expiry in force at the cutoff of ``window``, per account."""
    history = transactions.loc[
        transactions["transaction_date"].between(window.history_start, window.history_cutoff)
    ]
    ordered = order_transactions(history)
    return ordered.groupby("msno", sort=False)["membership_expire_date"].last()


def build_accounts(
    members: pd.DataFrame,
    transactions: pd.DataFrame,
    months: list[LabelWindow],
) -> pd.DataFrame:
    """Project the reference and the transactions onto the ``accounts`` table.

    Args:
        members: raw account reference.
        transactions: the concatenated transactions.
        months: labelling windows used to derive the termination dates.

    Returns:
        The ``accounts`` table, in contract shape.
    """
    # The trace is emitted whether or not the column was loaded. Not reading it
    # is precisely how a column gets dropped without anyone noticing, and the
    # rejection of ``bd`` is a decision that has to stay visible.
    for column, reason in REJECTED_COLUMNS.items():
        logger.warning(
            "source column rejected",
            extra={"column": column, "reason": reason, "loaded": column in members.columns},
        )

    plans = (
        transactions.sort_values(["msno", "transaction_date"])
        .groupby("msno", sort=False)[["payment_plan_days", "plan_list_price"]]
        .last()
    )
    accounts = members.loc[members["msno"].isin(transactions["msno"].unique())].copy()
    accounts = accounts.join(plans, on="msno")

    days = accounts["payment_plan_days"].fillna(30).clip(lower=1)
    accounts["mrr"] = (
        (accounts["plan_list_price"].fillna(0.0) / days * MONTHLY_BASIS_DAYS)
        .round(2)
        .clip(lower=0.0)
    )
    accounts["type_contrat"] = np.select(
        [days <= MONTHLY_PLAN_MAX_DAYS, days <= MULTIYEAR_PLAN_MAX_DAYS],
        [ContractType.MENSUEL.value, ContractType.PLURIANNUEL.value],
        default=ContractType.ANNUEL.value,
    )
    # City and registration channel are opaque codes. They are kept as
    # categories, mapped onto the contract vocabulary without being read as
    # meaningful segments, which they are not.
    segments = [member.value for member in Segment]
    channels = [member.value for member in AcquisitionChannel]
    accounts["segment"] = [
        segments[code % len(segments)] for code in accounts["city"].fillna(0).astype(int)
    ]
    accounts["canal_acquisition"] = [
        channels[code % len(channels)] for code in accounts["registered_via"].fillna(0).astype(int)
    ]

    started = pd.to_datetime(
        accounts["registration_init_time"].astype(int).astype(str),
        format=KKBOX_DATE_FORMAT,
        utc=True,
        errors="coerce",
    ).dt.as_unit("us")
    accounts["date_debut_contrat"] = started
    # ``reindex`` rather than ``map``: against an empty series of terminations,
    # ``map`` tries to cast the datetime column to float and raises. It happens
    # whenever no account churns in the window, a case the real dataset never
    # shows but a test does.
    terminations = _termination_dates(transactions, months)
    aligned = terminations.reindex(accounts["msno"].to_numpy())
    accounts["date_resiliation"] = pd.Series(
        aligned.to_numpy(), index=accounts.index, dtype="datetime64[us, UTC]"
    )
    accounts = accounts.rename(columns={"msno": "client_id"})

    # A termination before the registration is impossible and would breach the
    # contract. It signals a reference row the transactions contradict.
    inconsistent = accounts["date_resiliation"].notna() & (
        accounts["date_resiliation"] <= accounts["date_debut_contrat"]
    )
    if inconsistent.any():
        logger.warning(
            "terminations before registration dropped", extra={"rows": int(inconsistent.sum())}
        )
        accounts = accounts.loc[~inconsistent]

    columns = [name for name in ACCOUNTS_SCHEMA.column_names if name in accounts.columns]
    return accounts.loc[accounts["date_debut_contrat"].notna(), columns].reset_index(drop=True)


def _events_from_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Turn the transactions into contract events."""
    stamps = pd.to_datetime(
        transactions["transaction_date"].astype(int).astype(str),
        format=KKBOX_DATE_FORMAT,
        utc=True,
        errors="coerce",
    ).dt.as_unit("us")
    base = pd.DataFrame(
        {"client_id": transactions["msno"].to_numpy(), "event_ts": stamps.to_numpy()}
    )

    shortfall = transactions["plan_list_price"] - transactions["actual_amount_paid"]
    auto_renew_off = transactions["is_auto_renew"] == 0
    parts = [
        base.assign(
            event_type=EventType.FACTURE_EMISE.value,
            event_value=transactions["plan_list_price"].to_numpy(),
        ),
        base.loc[(shortfall > 0).to_numpy()].assign(
            event_type=EventType.ECHEC_PRELEVEMENT.value,
            event_value=shortfall.loc[shortfall > 0].to_numpy(),
        ),
        base.loc[(transactions["is_cancel"] == 1).to_numpy()].assign(
            event_type=EventType.ANNULATION_ABONNEMENT.value, event_value=1.0
        ),
        base.loc[auto_renew_off.to_numpy()].assign(
            event_type=EventType.DESACTIVATION_RENOUVELLEMENT.value, event_value=1.0
        ),
    ]
    return pd.concat(parts, ignore_index=True)


def _events_from_logs(logs: pd.DataFrame) -> pd.DataFrame:
    """Turn one chunk of listening logs into contract events."""
    stamps = pd.to_datetime(
        logs["date"].astype(int).astype(str), format=KKBOX_DATE_FORMAT, utc=True, errors="coerce"
    ).dt.as_unit("us")
    base = pd.DataFrame({"client_id": logs["msno"].to_numpy(), "event_ts": stamps.to_numpy()})

    played = logs[["num_25", "num_50", "num_75", "num_985", "num_100"]].sum(axis=1)
    completion = np.where(played > 0, logs["num_100"] / played.replace(0, np.nan), np.nan)
    return pd.concat(
        [
            base.assign(
                event_type=EventType.CONNEXION.value, event_value=logs["num_unq"].to_numpy()
            ),
            base.assign(
                event_type=EventType.USAGE_MODULE_CLE.value,
                event_value=(logs["total_secs"] / 60).to_numpy(),
            ),
            base.assign(event_type=EventType.TAUX_COMPLETION.value, event_value=completion),
        ],
        ignore_index=True,
    )


def build_events(
    transactions: pd.DataFrame,
    accounts: pd.DataFrame,
    log_chunks: Iterable[pd.DataFrame] = (),
    resolution: DatetimeResolution = "us",
) -> pd.DataFrame:
    """Project the transactions and the listening logs onto the ``events`` table.

    Events falling outside the contract window of their account are dropped here
    rather than left for the validator to reject: the window comes from the
    reference table this adapter has just built, so the trimming belongs to it.

    Args:
        transactions: the concatenated transactions.
        accounts: the ``accounts`` table already built.
        log_chunks: chunks of listening logs, possibly empty. A source without
            them stays conformant, it simply yields fewer features.
        resolution: target timestamp resolution.

    Returns:
        The ``events`` table, in contract shape.
    """
    parts = [_events_from_transactions(transactions)]
    parts.extend(_events_from_logs(chunk) for chunk in log_chunks)
    events = pd.concat(parts, ignore_index=True)
    events = events.loc[events["event_ts"].notna()]

    bounds = accounts.set_index("client_id")[["date_debut_contrat", "date_resiliation"]]
    joined = events.join(bounds, on="client_id")
    inside = joined["date_debut_contrat"].notna() & (
        joined["event_ts"] >= joined["date_debut_contrat"]
    )
    inside &= joined["date_resiliation"].isna() | (joined["event_ts"] <= joined["date_resiliation"])
    dropped = int((~inside).sum())
    if dropped:
        logger.info("events outside the contract window dropped", extra={"rows": dropped})

    events = events.loc[inside.to_numpy()].copy()
    events["event_ts"] = events["event_ts"].dt.as_unit(resolution)
    events["event_value"] = events["event_value"].astype("float64")
    return (
        events.loc[:, list(EVENTS_SCHEMA.column_names)]
        .sort_values(["client_id", "event_ts", "event_type"], kind="stable", ignore_index=True)
        .reset_index(drop=True)
    )


def build_dataset(
    paths: KkboxRawPaths,
    account_ids: set[str],
    months: list[LabelWindow],
    chunk_size: int = 1_000_000,
    resolution: DatetimeResolution = "us",
) -> Dataset:
    """Build both contract tables for one sample of accounts.

    Args:
        paths: resolved raw paths.
        account_ids: the drawn account sample.
        months: labelling windows used to derive the termination dates.
        chunk_size: rows per chunk when reading the logs.
        resolution: target timestamp resolution.

    Returns:
        The two contract tables.
    """
    transactions = load_transactions(paths, account_ids, chunk_size)
    members = pd.concat(
        list(
            read_in_chunks(
                paths.members,
                ["msno", "city", "registered_via", "registration_init_time"],
                account_ids,
                chunk_size,
            )
        ),
        ignore_index=True,
    )
    accounts = build_accounts(members, transactions, months)

    log_paths = [path for path in (paths.user_logs_history, paths.user_logs_recent) if path]
    chunks = [
        chunk
        for path in log_paths
        for chunk in read_in_chunks(path, _LOG_COLUMNS, account_ids, chunk_size)
    ]
    events = build_events(transactions, accounts, chunks, resolution)
    return Dataset(accounts=accounts, events=events)
