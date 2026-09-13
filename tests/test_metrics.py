"""Tests of the head of list metrics, on cases computed by hand."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from churn.evaluation.metrics import (
    lift,
    precision_at_k,
    precision_per_period,
    recall_at_k,
    roc_auc,
    top_k_mask,
)

WEEKLY = "W-MON"


def _ranking() -> pd.DataFrame:
    """Return two scoring weeks computed by hand.

    Week one, K = 2: the top two are C1 (0.9, lost) and C2 (0.8, kept), so the
    precision is 1 / 2. Week two, K = 2: the top two are D1 (0.7, lost) and D2
    (0.6, lost), so the precision is 2 / 2. The mean over weeks is 0.75.

    Positives: C1, C3, D1, D2, four in total. Captured in the tops: C1, D1, D2,
    so the pooled recall is 3 / 4.
    """
    week_one = pd.Timestamp("2025-03-03", tz="UTC")
    week_two = pd.Timestamp("2025-03-10", tz="UTC")
    return pd.DataFrame(
        {
            "T0": [week_one] * 4 + [week_two] * 3,
            "client_id": ["C1", "C2", "C3", "C4", "D1", "D2", "D3"],
            "mrr": [10.0, 20.0, 30.0, 40.0, 10.0, 20.0, 30.0],
            "y": [1, 0, 1, 0, 1, 1, 0],
            "score": [0.9, 0.8, 0.3, 0.1, 0.7, 0.6, 0.2],
        }
    )


def test_precision_at_k_matches_the_hand_computation() -> None:
    """Criterion 2 of lot 4."""
    assert precision_at_k(_ranking(), k=2, frequency=WEEKLY) == pytest.approx(0.75)


def test_precision_is_computed_per_period_not_globally() -> None:
    """A global top 2 would take C1 and C2, precision 0.5, and mean nothing."""
    per_period = precision_per_period(_ranking(), k=2, frequency=WEEKLY)
    assert list(per_period.round(4)) == [0.5, 1.0]


def test_recall_at_k_is_pooled_over_the_test_set() -> None:
    """Three positives captured out of four."""
    assert recall_at_k(_ranking(), k=2, frequency=WEEKLY) == pytest.approx(0.75)


def test_ties_are_broken_by_revenue_then_identifier() -> None:
    """Equal scores rank by revenue descending, then client identifier ascending.

    Two runs on the same data must name the same accounts.
    """
    tied = pd.DataFrame(
        {
            "T0": [pd.Timestamp("2025-03-03", tz="UTC")] * 3,
            "client_id": ["B", "A", "C"],
            "mrr": [50.0, 50.0, 90.0],
            "y": [0, 1, 0],
            "score": [0.5, 0.5, 0.5],
        }
    )
    chosen = tied.loc[top_k_mask(tied, k=2, frequency=WEEKLY), "client_id"]
    assert sorted(chosen) == ["A", "C"]


def test_a_short_period_counts_only_the_rows_it_has() -> None:
    """Two rows against K = 5: empty call slots are not misses."""
    short = _ranking().iloc[4:6]
    assert precision_at_k(short, k=5, frequency=WEEKLY) == pytest.approx(1.0)


def test_recall_is_undefined_without_any_positive() -> None:
    """Dividing by zero positives is reported as undefined, not as zero."""
    negatives = _ranking().assign(y=0)
    assert math.isnan(recall_at_k(negatives, k=2, frequency=WEEKLY))


def test_an_empty_frame_yields_an_undefined_precision() -> None:
    """The empty path does not crash."""
    assert math.isnan(precision_at_k(_ranking().head(0), k=2, frequency=WEEKLY))


def test_lift_against_the_reference() -> None:
    """A precision of 0.3 against 0.1 is a lift of three."""
    assert lift(0.3, 0.1) == pytest.approx(3.0)
    assert math.isnan(lift(0.3, 0.0))


def test_roc_auc_is_undefined_on_a_single_class() -> None:
    """Informational metric, never a crash."""
    assert math.isnan(roc_auc(_ranking().assign(y=1)))
    assert 0.0 <= roc_auc(_ranking()) <= 1.0


def test_a_random_like_ranking_scores_near_the_base_rate() -> None:
    """A score unrelated to the target has a precision close to the base rate."""
    rng = pd.Series(range(4000)).sample(frac=1.0, random_state=0).to_numpy()
    weeks = pd.date_range("2025-01-06", periods=40, freq="W-MON", tz="UTC")
    frame = pd.DataFrame(
        {
            "T0": [weeks[i % 40] for i in range(4000)],
            "client_id": [f"C{i:05d}" for i in range(4000)],
            "mrr": 1.0,
            "y": [1 if i % 10 == 0 else 0 for i in range(4000)],
            "score": rng.astype("float64"),
        }
    )
    assert precision_at_k(frame, k=50, frequency=WEEKLY) == pytest.approx(0.10, abs=0.03)
