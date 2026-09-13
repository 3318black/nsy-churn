"""Runs scorers through the chronological folds and gathers the measures.

Any scorer goes through the very same folds, the very same periods and the very
same K. The baselines of this lot and the model of lot 5 are therefore compared
on equal terms, which is the whole point of fixing the protocol first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from churn.evaluation.baselines import Scorer
from churn.evaluation.metrics import (
    precision_at_k,
    precision_per_period,
    recall_at_k,
    roc_auc,
)
from churn.evaluation.splitting import TemporalFold
from churn.features.build import TrainingSet

__all__ = ["EvaluationResult", "evaluate_scorers", "summarise"]

#: Classes a training fold must hold for any comparison to mean something.
_BINARY_CLASSES = 2


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Measures gathered over every fold and every scorer.

    Attributes:
        folds: one row per fold and scorer.
        periods: one row per fold, scorer and scoring period.
        k: handling capacity the measures were taken at.
    """

    folds: pd.DataFrame
    periods: pd.DataFrame
    k: int


def evaluate_scorers(
    training: TrainingSet,
    folds: Sequence[TemporalFold],
    scorers: Sequence[Scorer],
    k: int,
    frequency: str,
) -> EvaluationResult:
    """Evaluate each scorer on each fold.

    Args:
        training: the grid, its target and its features.
        folds: the chronological folds.
        scorers: the scorers to compare.
        k: handling capacity per period.
        frequency: scoring period frequency.

    Returns:
        The gathered measures.

    Raises:
        ValueError: when a training fold holds a single class. Measured on KKBox
            before decision D17: every fold trained on zero positives, and the
            logistic baseline silently reproduced the revenue ranking. A
            comparison on such a fold is a number, not a measure.
    """
    fold_rows: list[dict[str, object]] = []
    period_frames: list[pd.DataFrame] = []

    for fold in folds:
        train = TrainingSet(
            grid=training.grid.iloc[fold.train_index],
            target=training.target.iloc[fold.train_index],
            features=training.features.iloc[fold.train_index],
        )
        test_features = training.features.iloc[fold.test_index]
        test_grid = training.grid.iloc[fold.test_index]
        train_positives = int(train.target.sum())
        if train.target.nunique() < _BINARY_CLASSES:
            message = (
                f"fold {fold.index} trains on {len(train.target)} rows holding a single "
                f"class ({train_positives} positives): every comparison on it would be "
                f"meaningless"
            )
            raise ValueError(message)
        # The test target never reaches a scorer, not even through the grid.
        blind_grid = test_grid.drop(columns="y")

        for scorer in scorers:
            scores = scorer.fit_score(train, test_features, blind_grid)
            ranking = test_grid[["T0", "client_id", "mrr", "y"]].assign(score=scores)
            fold_rows.append(
                {
                    "fold": fold.index,
                    "scorer": scorer.name,
                    "test_start": fold.test_start,
                    "test_end": fold.test_end,
                    "train_rows": len(fold.train_index),
                    "train_positives": train_positives,
                    "test_rows": len(fold.test_index),
                    "test_positive_rate": float(test_grid["y"].mean()),
                    "precision_at_k": precision_at_k(ranking, k, frequency),
                    "recall_at_k": recall_at_k(ranking, k, frequency),
                    "roc_auc": roc_auc(ranking),
                }
            )
            per_period = precision_per_period(ranking, k, frequency).reset_index()
            per_period.columns = ["period", "precision"]
            period_frames.append(per_period.assign(fold=fold.index, scorer=scorer.name))

    periods = (
        pd.concat(period_frames, ignore_index=True)
        if period_frames
        else pd.DataFrame(columns=["period", "precision", "fold", "scorer"])
    )
    return EvaluationResult(folds=pd.DataFrame(fold_rows), periods=periods, k=k)


def summarise(result: EvaluationResult, reference: str = "revenue") -> pd.DataFrame:
    """Return one row per scorer, averaged over the folds.

    The lift is expressed against the revenue ranking by default: it is what a
    salesperson achieves without any tool, hence the comparison that matters.

    Args:
        result: the gathered measures.
        reference: name of the scorer the lift is computed against.

    Returns:
        Mean and spread of each measure, plus the lift, one row per scorer.
    """
    if result.folds.empty:
        return pd.DataFrame()
    grouped = result.folds.groupby("scorer", sort=False)
    summary = pd.DataFrame(
        {
            "precision_at_k": grouped["precision_at_k"].mean(),
            "precision_at_k_std": grouped["precision_at_k"].std(ddof=0),
            "recall_at_k": grouped["recall_at_k"].mean(),
            "roc_auc": grouped["roc_auc"].mean(),
            "base_rate": grouped["test_positive_rate"].mean(),
            "folds": grouped.size(),
        }
    )
    if reference in summary.index:
        reference_precision = float(summary["precision_at_k"].to_dict()[reference])
        summary["lift_vs_" + reference] = summary["precision_at_k"] / reference_precision
    return summary.reset_index()
