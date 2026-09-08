"""Generator of raw timestamped events, for the automated tests.

Its role is narrow and stated in decision D14: it feeds the tests, never the
demonstration. What it buys there is reproducibility, speed, and coverage of the
edge cases a real dataset does not contain on demand.

It writes the two raw tables and never a feature. Generating "tickets over the
last 30 days" straight away would remove the very step that concentrates the risk
of the project, the construction of windows without leakage. That is decision D3.

**It must produce a hard problem, not a comfortable one.** Four properties matter
more than realism.

``unpredictable_churn_share``
    A share of terminations carries no precursor at all. It caps the reachable
    performance, and without it a model would look brilliant on a world built to
    be guessed.
``duplicate_timestamp_rate``
    Several events share one timestamp for one account. That exact case produced
    10.5% of wrong rows in a measurement dated 2026-09-07, without raising
    anything. The generator has to produce it so the later lots have something to
    catch.
``missing_data_rate``
    Missing values and observation gaps, because no real source is complete.
``noise``
    Accounts showing every warning sign and never terminating.

Determinism is strict: two runs with the same seed produce identical frames, row
order included.

**Known limitation, seen on 2026-09-08 in the distribution report.** The finance
family separates the two classes almost perfectly: a failed direct debit is only
ever emitted inside the signal window of an account that will terminate, so a
model reading it would look brilliant. This is a weakness of the simulation, not
of the pipeline, and it is why decision D14 confines this generator to the tests
and forbids it from carrying any performance figure. Emitting incidents on
healthy accounts too would make the simulated problem honest, and it is the first
thing to fix should this jeu ever serve a measurement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

import numpy as np
import pandas as pd

from churn.config import SyntheticSourceConfig
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

__all__ = ["ChurnProfile", "GeneratorSettings", "generate_dataset"]


class ChurnProfile(IntEnum):
    """Behaviour an account follows before it terminates.

    ``NONE`` also covers the accounts that never terminate.
    """

    NONE = 0
    #: Terminates with no precursor at all, the ceiling of reachable performance.
    SILENT = 1
    #: Support relationship degrades: more tickets, slower resolutions.
    SUPPORT = 2
    #: Product disengagement: fewer connections, less usage.
    PRODUCT = 3
    #: Payment incidents: late payments, failed direct debits.
    FINANCE = 4


@dataclass(frozen=True, slots=True)
class GeneratorSettings:
    """Knobs that shape the difficulty of the generated problem.

    They are deliberately not in ``config.yaml``: they tune the simulation, not
    the pipeline, and no business decision rests on them.

    Attributes:
        signal_window_days: how long before termination the degradation starts.
        false_signal_share: share of surviving accounts that show the same
            degradation and never terminate. This is the noise floor.
        base_connection_rate: mean daily connections of a healthy account.
        weekend_factor: multiplier applied on Saturday and Sunday.
        degraded_factor: multiplier applied inside the signal window.
        support_ticket_rate: mean daily tickets of a healthy account.
        min_observation_days: shortest history an account may carry.
    """

    signal_window_days: int = 75
    false_signal_share: float = 0.12
    base_connection_rate: float = 0.55
    weekend_factor: float = 0.45
    degraded_factor: float = 3.0
    support_ticket_rate: float = 0.004
    min_observation_days: int = 120


@dataclass(frozen=True, slots=True)
class _Population:
    """Accounts plus the internal arrays the generation needs afterwards.

    They are returned explicitly rather than stashed in ``DataFrame.attrs``:
    pandas tries to serialise ``attrs`` when writing Parquet, and a numpy array
    is not JSON serialisable. Hiding internals there also makes them travel
    invisibly to callers that have no business seeing them.

    Attributes:
        accounts: the account reference table.
        churn_profile: behaviour followed by each account before termination.
        signal_end: instant the degradation window ends at, the termination date
            for a churner and the end of history for a faking survivor.
    """

    accounts: pd.DataFrame
    churn_profile: np.ndarray
    signal_end: np.ndarray


def _draw_accounts(
    rng: np.random.Generator,
    profile: SyntheticSourceConfig,
    settings: GeneratorSettings,
) -> _Population:
    """Draw the account reference table and the termination dates.

    The time to termination follows an exponential law whose rate is the annual
    churn rate, so the empirical rate per account year matches the configured one
    by construction rather than by tuning.
    """
    n = profile.n_accounts
    # Naive timestamps inside the generator, localised once at the very end.
    # A tz aware series returns an object array through ``to_numpy``, which
    # cannot take part in the vectorised date arithmetic below.
    start = pd.Timestamp(profile.history_start)
    end = pd.Timestamp(profile.history_end)
    span_days = (end - start).days

    latest_start = span_days - settings.min_observation_days
    offsets = rng.integers(0, max(latest_start, 1), size=n)
    began = (start.to_numpy() + offsets * np.timedelta64(1, "D")).astype("datetime64[us]")
    observed_years = ((end.to_numpy() - began) / np.timedelta64(1, "D")) / 365.25

    # Exponential time to termination, rate = annual churn rate.
    rate = max(profile.annual_churn_rate, 1e-9)
    years_to_churn = rng.exponential(1.0 / rate, size=n)
    churns = years_to_churn < observed_years
    # At least one day of contract before a termination. Rounding a very short
    # time to churn down to zero would place the termination on the very day
    # the contract starts, which the contract refuses. It happened on two
    # accounts out of five thousand, a rate no small sample would surface.
    days_to_churn = np.maximum(np.rint(years_to_churn * 365.25), 1.0)
    churn_offsets = np.where(churns, days_to_churn, 0).astype(np.int64)
    ended = began + churn_offsets * np.timedelta64(1, "D")
    # The unit is explicit: a bare ``datetime64("NaT")`` carries the generic
    # unit, which numpy deprecates and will refuse.
    terminated = np.where(churns, ended, np.datetime64("NaT", "us"))

    # Profiles: a share of the churners carry no precursor, the rest split
    # evenly across the three families of signal.
    profiles = np.zeros(n, dtype=np.int64)
    churn_index = np.flatnonzero(churns)
    silent = rng.random(churn_index.size) < profile.unpredictable_churn_share
    profiles[churn_index[silent]] = ChurnProfile.SILENT
    loud = churn_index[~silent]
    profiles[loud] = rng.choice(
        [ChurnProfile.SUPPORT, ChurnProfile.PRODUCT, ChurnProfile.FINANCE],
        size=loud.size,
    )

    # Noise: survivors that show the same degradation and never terminate.
    survivors = np.flatnonzero(~churns)
    faking = survivors[rng.random(survivors.size) < settings.false_signal_share]
    profiles[faking] = rng.choice(
        [ChurnProfile.SUPPORT, ChurnProfile.PRODUCT, ChurnProfile.FINANCE],
        size=faking.size,
    )

    accounts = pd.DataFrame(
        {
            "client_id": [f"C{index:06d}" for index in range(n)],
            "date_debut_contrat": began,
            "date_resiliation": terminated,
            "type_contrat": rng.choice([member.value for member in ContractType], size=n),
            "mrr": np.round(rng.gamma(shape=2.0, scale=90.0, size=n), 2),
            "segment": rng.choice([member.value for member in Segment], size=n),
            "canal_acquisition": rng.choice(
                [member.value for member in AcquisitionChannel], size=n
            ),
            "nb_licences": rng.integers(1, 60, size=n),
        }
    )
    # The end of the signal window is the termination date for a churner, and the
    # end of history for a surviving account that only fakes the signal.
    signal_end = np.where(churns, ended, end.to_numpy())
    return _Population(accounts=accounts, churn_profile=profiles, signal_end=signal_end)


def _daily_grid(
    accounts: pd.DataFrame, signal_end: np.ndarray, history_end: pd.Timestamp
) -> pd.DataFrame:
    """Return one row per account and per observed day.

    Built by repetition rather than by a loop over accounts: the frame reaches
    several million rows and a Python loop would be unusable.
    """
    began = accounts["date_debut_contrat"].to_numpy()
    terminated = accounts["date_resiliation"]
    ended = terminated.fillna(history_end).to_numpy()
    # A terminated account stops the day before its termination. Events are drawn
    # inside working hours, so keeping the termination day would place them after
    # the termination timestamp, which sits at midnight, and breach the contract.
    last_day = np.where(terminated.notna().to_numpy(), ended - np.timedelta64(1, "D"), ended)
    lengths = ((last_day - began) / np.timedelta64(1, "D")).astype(np.int64) + 1
    lengths = np.maximum(lengths, 1)

    account_index = np.repeat(np.arange(len(accounts)), lengths)
    offsets = np.concatenate([np.arange(length) for length in lengths])
    days = began[account_index] + offsets * np.timedelta64(1, "D")

    days_to_end = (signal_end[account_index] - days) / np.timedelta64(1, "D")

    return pd.DataFrame(
        {
            "account_index": account_index,
            "day": days,
            "weekday": pd.DatetimeIndex(days).dayofweek.to_numpy(),
            "days_to_end": days_to_end,
        }
    )


@dataclass(frozen=True, slots=True)
class _Emitter:
    """Draws event rows on the daily grid.

    Carries the state shared by every event type so that emitting one type takes
    four arguments instead of seven, and reads as what it is.

    Attributes:
        rng: seeded generator, the single source of randomness.
        grid: one row per account and per observed day.
        client_ids: identifier of each account, indexed like the grid.
    """

    rng: np.random.Generator
    grid: pd.DataFrame
    client_ids: np.ndarray

    def emit(
        self,
        mask: np.ndarray,
        rates: np.ndarray,
        event_type: EventType,
        value_fn: Callable[[np.random.Generator, int], np.ndarray],
        *,
        day_granular: bool = False,
    ) -> pd.DataFrame:
        """Draw a Poisson count per eligible day and expand it into event rows.

        Args:
            mask: days the event type may occur on.
            rates: mean daily count, per grid row.
            event_type: type of the emitted events.
            value_fn: draws the payload of the emitted events.
            day_granular: place the events at midnight rather than during
                working hours. Billing systems date to the day, and KKBox does
                so for every one of its events. Without this the journal would
                never carry an event landing exactly on an observation date, and
                the strict bound of the windows would never be exercised.

        Returns:
            The emitted rows, in contract shape.
        """
        counts = np.zeros(len(self.grid), dtype=np.int64)
        if mask.any():
            counts[mask] = self.rng.poisson(rates[mask])
        if not counts.any():
            return pd.DataFrame(columns=["client_id", "event_ts", "event_type", "event_value"])

        row_index = np.repeat(np.arange(len(self.grid)), counts)
        total = row_index.size
        days = self.grid["day"].to_numpy()[row_index]
        if day_granular:
            stamps = days
        else:
            # Spread over working hours, so the journal carries a real time of
            # day rather than midnight everywhere.
            minutes = self.rng.integers(8 * 60, 20 * 60, size=total)
            stamps = days + minutes * np.timedelta64(1, "m")
        accounts_of_rows = self.grid["account_index"].to_numpy()[row_index]
        return pd.DataFrame(
            {
                "client_id": self.client_ids[accounts_of_rows],
                "event_ts": stamps,
                "event_type": event_type.value,
                "event_value": value_fn(self.rng, total),
            }
        )


def _degradation(grid: pd.DataFrame, profiles: np.ndarray, family: ChurnProfile, window: int):
    """Return the mask of days inside the signal window of a given family."""
    account_profiles = profiles[grid["account_index"].to_numpy()]
    inside = (grid["days_to_end"].to_numpy() >= 0) & (grid["days_to_end"].to_numpy() <= window)
    return (account_profiles == family) & inside


def generate_dataset(
    profile: SyntheticSourceConfig,
    seed: int,
    resolution: DatetimeResolution = "us",
    settings: GeneratorSettings | None = None,
) -> Dataset:
    """Generate a synthetic dataset conforming to the contract.

    Args:
        profile: synthetic profile of the configuration.
        seed: seed of the generator. Two runs with the same seed produce
            identical frames, row order included.
        resolution: timestamp resolution of the output.
        settings: difficulty knobs of the simulation.

    Returns:
        The two contract tables.
    """
    settings = settings or GeneratorSettings()
    rng = np.random.default_rng(seed)
    history_end = pd.Timestamp(profile.history_end)

    population = _draw_accounts(rng, profile, settings)
    accounts = population.accounts
    profiles = population.churn_profile
    grid = _daily_grid(accounts, population.signal_end, history_end)

    weekend = np.isin(grid["weekday"].to_numpy(), (5, 6))
    seasonal = np.where(weekend, settings.weekend_factor, 1.0)
    everywhere = np.ones(len(grid), dtype=bool)
    emitter = _Emitter(rng=rng, grid=grid, client_ids=accounts["client_id"].to_numpy())

    product_drop = _degradation(grid, profiles, ChurnProfile.PRODUCT, settings.signal_window_days)
    support_up = _degradation(grid, profiles, ChurnProfile.SUPPORT, settings.signal_window_days)
    finance_bad = _degradation(grid, profiles, ChurnProfile.FINANCE, settings.signal_window_days)

    def gamma(shape: float, scale: float):
        def draw(generator: np.random.Generator, size: int) -> np.ndarray:
            return np.round(generator.gamma(shape, scale, size=size), 3)

        return draw

    def constant(value: float):
        def draw(_: np.random.Generator, size: int) -> np.ndarray:
            return np.full(size, value)

        return draw

    connection_rate = settings.base_connection_rate * seasonal
    connection_rate = np.where(product_drop, connection_rate * 0.15, connection_rate)
    usage_rate = connection_rate * 0.8
    ticket_rate = np.where(
        support_up,
        settings.support_ticket_rate * settings.degraded_factor * 4,
        settings.support_ticket_rate,
    )

    parts = [
        emitter.emit(everywhere, connection_rate, EventType.CONNEXION, gamma(2.0, 3.0)),
        emitter.emit(
            everywhere,
            usage_rate,
            EventType.USAGE_MODULE_CLE,
            gamma(2.0, 12.0),
        ),
        emitter.emit(
            everywhere,
            ticket_rate,
            EventType.TICKET_SUPPORT_OUVERT,
            gamma(1.5, 1.2),
        ),
        emitter.emit(
            support_up,
            np.full(len(grid), settings.support_ticket_rate * 2),
            EventType.TICKET_SUPPORT_RESOLU,
            gamma(3.0, 9.0),
        ),
        emitter.emit(
            everywhere,
            np.full(len(grid), 1 / 30.0),
            EventType.FACTURE_EMISE,
            gamma(2.0, 90.0),
            day_granular=True,
        ),
        emitter.emit(
            finance_bad,
            np.full(len(grid), 1 / 25.0),
            EventType.ECHEC_PRELEVEMENT,
            gamma(2.0, 60.0),
            day_granular=True,
        ),
        emitter.emit(
            finance_bad,
            np.full(len(grid), 1 / 20.0),
            EventType.FACTURE_PAYEE,
            gamma(4.0, 6.0),
            day_granular=True,
        ),
        emitter.emit(
            everywhere,
            np.full(len(grid), 1 / 400.0),
            EventType.CONTACT_COMMERCIAL,
            gamma(2.0, 8.0),
        ),
        emitter.emit(
            product_drop,
            np.full(len(grid), 1 / 90.0),
            EventType.DESACTIVATION_MODULE,
            constant(1.0),
        ),
    ]
    events = pd.concat([part for part in parts if not part.empty], ignore_index=True)

    # Duplicated timestamps for one account. Not decorative: this exact case
    # produced 10.5% of wrong rows in the measurement of 2026-09-07.
    if profile.duplicate_timestamp_rate > 0 and len(events):
        picked = rng.random(len(events)) < profile.duplicate_timestamp_rate
        if picked.any():
            events = pd.concat([events, events.loc[picked]], ignore_index=True)

    # Missing values and observation gaps, because no real source is complete.
    if profile.missing_data_rate > 0 and len(events):
        blanked = rng.random(len(events)) < profile.missing_data_rate
        events.loc[blanked, "event_value"] = np.nan
        dropped = rng.random(len(events)) < profile.missing_data_rate
        events = events.loc[~dropped].reset_index(drop=True)

    events = events.sort_values(
        ["client_id", "event_ts", "event_type"], kind="stable", ignore_index=True
    )

    accounts = accounts.loc[:, list(ACCOUNTS_SCHEMA.column_names)].copy()
    events = events.loc[:, list(EVENTS_SCHEMA.column_names)].copy()
    for frame, schema in ((accounts, ACCOUNTS_SCHEMA), (events, EVENTS_SCHEMA)):
        for spec in schema.timestamp_columns:
            # ``dt.as_unit`` rather than ``astype`` with an f-string: the dtype
            # is dynamic and the pandas stubs only type the literal overloads.
            naive = frame[spec.name].dt.as_unit(resolution)
            frame[spec.name] = naive.dt.tz_localize("UTC")
    accounts["nb_licences"] = accounts["nb_licences"].astype("int64")
    events["event_value"] = events["event_value"].astype("float64")

    return Dataset(accounts=accounts, events=events)
