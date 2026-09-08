"""Tests of the synthetic generator and of the source interface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from churn.config import AppConfig, SyntheticSourceConfig
from churn.data.schemas import Dataset, EventType
from churn.data.sources import (
    ParquetDataSource,
    SourceDescription,
    read_dataset,
    write_dataset,
)
from churn.data.synthetic import generate_dataset
from churn.data.validate import validate_dataset

#: Sample size of the sizeable cases. Below roughly a thousand accounts the
#: sampling error on the churn rate exceeds ten percent, see the tolerance
#: discussion in :func:`test_annual_churn_rate_matches_the_configured_one`.
SAMPLE_ACCOUNTS = 1500

#: Sample size of the cheap cases, where only the shape of the output matters.
SMALL_ACCOUNTS = 150


@pytest.fixture(scope="module")
def profile(config: AppConfig) -> SyntheticSourceConfig:
    """Return the synthetic profile, shrunk to keep the suite fast."""
    return config.sources.synthetic.model_copy(update={"n_accounts": SAMPLE_ACCOUNTS})


@pytest.fixture(scope="module")
def dataset(profile: SyntheticSourceConfig, config: AppConfig) -> Dataset:
    """Generate one dataset shared by the module, generation is not free."""
    return generate_dataset(
        profile,
        seed=config.project.random_seed,
        resolution=config.features.datetime_resolution,
    )


def test_generated_dataset_conforms_to_the_contract(dataset: Dataset, config: AppConfig) -> None:
    """Criterion 1 of lot 1, the whole point of the generator."""
    report = validate_dataset(dataset, resolution=config.features.datetime_resolution)
    assert report.is_valid, report.render()


def test_generation_is_reproducible(profile: SyntheticSourceConfig) -> None:
    """Criterion 3 of lot 1: same seed, identical frames, row order included."""
    first = generate_dataset(profile.model_copy(update={"n_accounts": SMALL_ACCOUNTS}), seed=7)
    second = generate_dataset(profile.model_copy(update={"n_accounts": SMALL_ACCOUNTS}), seed=7)
    assert first.accounts.equals(second.accounts)
    assert first.events.equals(second.events)


def test_another_seed_yields_another_dataset(profile: SyntheticSourceConfig) -> None:
    """Reproducibility must not come from a constant output."""
    first = generate_dataset(profile.model_copy(update={"n_accounts": SMALL_ACCOUNTS}), seed=7)
    second = generate_dataset(profile.model_copy(update={"n_accounts": SMALL_ACCOUNTS}), seed=8)
    assert not first.events.equals(second.events)


def test_annual_churn_rate_matches_the_configured_one(
    dataset: Dataset, profile: SyntheticSourceConfig
) -> None:
    """Criterion 5 of lot 1, with the tolerance justified rather than tuned.

    The rate is the number of terminations per account year, which is the hazard
    rate the generator draws from. The tolerance is set by sampling error: with
    roughly 235 terminations at this sample size, the relative standard deviation
    is about ``1 / sqrt(235)``, near 6.5%. A tolerance of 20% is therefore close
    to three standard deviations, wide enough never to fail by chance and tight
    enough to catch a generator that drifts.
    """
    accounts = dataset.accounts
    end_of_history = pd.Timestamp(profile.history_end, tz="UTC")
    observed_until = accounts["date_resiliation"].fillna(end_of_history)
    account_years = ((observed_until - accounts["date_debut_contrat"]).dt.days / 365.25).sum()
    terminations = int(accounts["date_resiliation"].notna().sum())

    assert terminations > 100, "sample too small for the tolerance below to hold"
    observed = terminations / account_years
    assert observed == pytest.approx(profile.annual_churn_rate, rel=0.20)


def test_a_share_of_terminations_carries_no_precursor(dataset: Dataset) -> None:
    """The ceiling of reachable performance must exist, see decision D2.

    A generator whose every termination is announced would let a model look
    brilliant on a world built to be guessed.
    """
    accounts = dataset.accounts
    events = dataset.events
    terminated = accounts.loc[accounts["date_resiliation"].notna()]
    window_start = terminated["date_resiliation"] - pd.Timedelta(days=75)
    bounds = pd.DataFrame(
        {
            "client_id": terminated["client_id"],
            "start": window_start,
            "end": terminated["date_resiliation"],
        }
    ).set_index("client_id")

    signals = events.loc[
        events["event_type"].isin(
            [
                EventType.TICKET_SUPPORT_OUVERT.value,
                EventType.ECHEC_PRELEVEMENT.value,
                EventType.DESACTIVATION_MODULE.value,
            ]
        )
    ]
    joined = signals.join(bounds, on="client_id", how="inner")
    inside = joined.loc[
        (joined["event_ts"] >= joined["start"]) & (joined["event_ts"] <= joined["end"])
    ]
    announced = set(inside["client_id"])
    silent_share = 1 - len(announced) / len(terminated)
    assert silent_share > 0.15, "every termination is announced, the problem is too easy"


def test_termination_never_falls_on_the_start_date(profile: SyntheticSourceConfig) -> None:
    """A very short time to churn must not round down to a same day termination.

    The default rate produces the case on roughly two accounts out of five
    thousand, which no small sample would surface. Raising the rate forces many
    short lives at once, so the guard is exercised rather than hoped for.
    """
    impatient = profile.model_copy(update={"annual_churn_rate": 0.99, "n_accounts": 800})
    accounts = generate_dataset(impatient, seed=3).accounts
    terminated = accounts.loc[accounts["date_resiliation"].notna()]

    assert len(terminated) > 200, "sample too small to exercise the guard"
    assert (terminated["date_resiliation"] > terminated["date_debut_contrat"]).all()


def test_duplicate_timestamps_are_produced(dataset: Dataset) -> None:
    """The case that produced 10.5% of wrong rows in the 2026-09-07 measurement.

    The later lots need the generator to fabricate it, otherwise their guard has
    nothing to catch.
    """
    duplicated = dataset.events.duplicated(["client_id", "event_ts"], keep=False)
    assert duplicated.any()
    assert duplicated.mean() > 0.05


def test_missing_values_are_produced(dataset: Dataset, profile: SyntheticSourceConfig) -> None:
    """No real source is complete, the generated one must not be either."""
    assert dataset.events["event_value"].isna().mean() == pytest.approx(
        profile.missing_data_rate, abs=0.03
    )


def test_weekly_seasonality_is_present(dataset: Dataset) -> None:
    """Weekend activity is lower, which the rolling windows will have to absorb."""
    connections = dataset.events.loc[dataset.events["event_type"] == EventType.CONNEXION.value]
    weekday = connections["event_ts"].dt.dayofweek
    weekend_mean = (weekday >= 5).sum() / 2
    week_mean = (weekday < 5).sum() / 5
    assert weekend_mean < week_mean


def test_no_feature_is_generated(dataset: Dataset) -> None:
    """Decision D3: raw dated events only, never an aggregate."""
    assert set(dataset.events.columns) == {
        "client_id",
        "event_ts",
        "event_type",
        "event_value",
    }


def test_roundtrip_through_parquet_preserves_the_dataset(
    dataset: Dataset, tmp_path: Path, config: AppConfig
) -> None:
    """The shared tail of every adapter: convert once, then read Parquet."""
    small = Dataset(dataset.accounts.head(50), dataset.events.head(500))
    written = write_dataset(small, tmp_path)
    assert set(written) == {"accounts", "events"}

    reloaded = read_dataset(tmp_path, config.features.datetime_resolution)
    assert reloaded.accounts.equals(small.accounts)
    assert reloaded.events.equals(small.events)


def test_source_description_travels_with_the_data(config: AppConfig) -> None:
    """is_synthetic reaches the reports, decision D2 rests on it."""
    description = SourceDescription.from_profile("synthetic", config.sources.synthetic)
    assert description.is_synthetic is True
    assert description.horizon_days == config.sources.synthetic.horizon_days

    active = ParquetDataSource.from_config(config)
    assert active.description.key == config.active_source
    assert active.description.is_synthetic is False
    assert active.description.horizon_days == 30


def test_reading_a_missing_table_fails_explicitly(tmp_path: Path) -> None:
    """A missing table is named, never silently treated as empty."""
    with pytest.raises(FileNotFoundError, match="accounts"):
        read_dataset(tmp_path, "us")
