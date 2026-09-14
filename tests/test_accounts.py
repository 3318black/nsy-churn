"""Tests of the account profile and of the suggested actions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from churn.config import AppConfig, FeatureMappingEntry, load_feature_mapping
from churn.interface.accounts import account_profile, suggested_actions
from churn.models.explain import factor_labels


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path]:
    """Write a reference and a journal for two accounts."""
    accounts = pd.DataFrame(
        {
            "client_id": ["A", "B"],
            "date_debut_contrat": pd.to_datetime(["2024-01-01", "2024-06-01"], utc=True),
        }
    )
    stamps = [
        "2025-01-02 10:00",  # usage, more than 30 days before the scoring date
        "2025-01-20 00:00",  # invoice, auto renewal disabled on the same transaction
        "2025-01-20 00:00",
        "2025-02-05 09:00",  # usage within the last 30 days
        "2025-02-05 18:00",  # same day, counted once
        "2025-02-10 11:00",  # usage within the last 30 days
        "2025-02-12 00:00",  # cancellation
        "2025-02-17 00:00",  # on the scoring date itself, excluded
        "2025-02-20 12:00",  # after the scoring date, excluded
    ]
    events = pd.DataFrame(
        {
            "client_id": ["A"] * len(stamps),
            "event_ts": pd.to_datetime(stamps, utc=True).as_unit("us"),
            "event_type": [
                "connexion",
                "facture_emise",
                "desactivation_renouvellement",
                "connexion",
                "connexion",
                "connexion",
                "annulation_abonnement",
                "facture_emise",
                "connexion",
            ],
            "event_value": [2.0, 149.0, 1.0, 3.0, 1.0, 4.0, 1.0, 180.0, 5.0],
        }
    )
    accounts_path = tmp_path / "accounts.parquet"
    events_path = tmp_path / "events.parquet"
    accounts.to_parquet(accounts_path)
    events.to_parquet(events_path)
    return accounts_path, events_path


SCORING_DATE = pd.Timestamp("2025-02-17", tz="UTC")


def test_the_profile_holds_only_what_was_known_before_the_scoring_date(
    files: tuple[Path, Path],
) -> None:
    """The invoice of the scoring date and the usage after it do not count."""
    profile = account_profile(*files, "A", SCORING_DATE)
    assert profile.registered == date(2024, 1, 1)
    assert profile.tenure_days == (date(2025, 2, 17) - date(2024, 1, 1)).days
    assert profile.last_usage == date(2025, 2, 10)
    assert profile.days_since_usage == 7
    assert profile.active_days_recent == 2
    assert profile.last_payment == date(2025, 1, 20)
    assert profile.last_payment_amount == 149.0
    assert profile.cancellations == 1
    assert profile.auto_renew_disabled == 1


def test_an_account_without_events_keeps_its_registration(files: tuple[Path, Path]) -> None:
    """Account B has no event: its profile says so, without inventing anything."""
    profile = account_profile(*files, "B", SCORING_DATE)
    assert profile.registered == date(2024, 6, 1)
    assert profile.last_usage is None
    assert profile.active_days_recent == 0
    assert profile.cancellations == 0
    assert not profile.is_empty


def test_missing_files_yield_an_empty_profile(tmp_path: Path) -> None:
    """The KKBox source online publishes no journal, which is not an error."""
    profile = account_profile(tmp_path / "a.parquet", tmp_path / "e.parquet", "A", SCORING_DATE)
    assert profile.is_empty


@pytest.fixture(scope="module")
def mapping(config: AppConfig) -> dict[str, FeatureMappingEntry]:
    """The business mapping of the repository."""
    return load_feature_mapping(config.paths.feature_mapping)


def test_actions_are_keyed_by_the_label_the_export_prints(
    mapping: dict[str, FeatureMappingEntry],
) -> None:
    """A label printed by the export must find its action in the interface."""
    actions = suggested_actions(mapping)
    printed = factor_labels(pd.DataFrame({"facteur_risque_1": ["connexion"]}), mapping)
    label = printed.iloc[0, 0]
    assert actions[label] == mapping["connexion"].action


def test_structural_factors_carry_no_action(mapping: dict[str, FeatureMappingEntry]) -> None:
    """Decision D19: no action for the account age or its revenue."""
    printed = factor_labels(
        pd.DataFrame({"facteur_risque_1": ["mrr", "anciennete_jours"]}), mapping
    )
    assert not set(printed["facteur_risque_1"]) & set(suggested_actions(mapping))
