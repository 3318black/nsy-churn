"""Head of list metrics, decision D5.

K is the weekly handling capacity of a sales team. A top K taken over the whole
test period would mean nothing to anyone: nobody calls fifty customers over a
quarter. Precision@K is therefore computed **per scoring period**, then
averaged. The figure reads directly as the hit rate a salesperson sees in the
Monday list.

Three conventions, each decided rather than left to chance.

Deterministic ties
    Rows are ordered by score descending, then revenue descending, then client
    identifier ascending, as the output contract requires. Two runs on the same
    data rank the same accounts.
Short periods
    A period holding fewer than K rows contributes the precision of the rows it
    has. Padding it to K would count empty call slots as misses.
Pooled recall
    Recall at K divides every captured positive by every positive of the test
    set. Averaging per period would give a week with one positive the weight of
    a week with forty.

ROC-AUC is computed for information only. On a rare class it stays flattering
while the head of the list, the only part anyone acts on, may be poor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

__all__ = [
    "RANKING_COLUMNS",
    "assign_periods",
    "lift",
    "precision_at_k",
    "precision_per_period",
    "recall_at_k",
    "roc_auc",
    "top_k_mask",
]

#: Columns a ranking frame must carry.
RANKING_COLUMNS = ("T0", "client_id", "mrr", "y", "score")

#: Classes a ROC curve needs.
_BINARY_CLASSES = 2


def assign_periods(frame: pd.DataFrame, frequency: str) -> pd.Series:
    """Return the scoring period of each row.

    Args:
        frame: a ranking frame.
        frequency: pandas period frequency, from ``evaluation.scoring_period``.

    Returns:
        The period of each row, aligned on ``frame``.
    """
    dates = frame["T0"]
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)
    return dates.dt.to_period(frequency)


def _ranked(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """Return the frame ordered within each period, with a zero based rank."""
    ranked = frame.assign(_period=assign_periods(frame, frequency))
    ranked = ranked.sort_values(
        ["_period", "score", "mrr", "client_id"],
        ascending=[True, False, False, True],
        kind="stable",
    )
    ranked["_rank"] = ranked.groupby("_period", sort=False).cumcount()
    return ranked


def top_k_mask(frame: pd.DataFrame, k: int, frequency: str) -> pd.Series:
    """Return whether each row belongs to the top K of its period.

    Args:
        frame: a ranking frame.
        k: handling capacity per period.
        frequency: pandas period frequency.

    Returns:
        A boolean series aligned on ``frame``.
    """
    ranked = _ranked(frame, frequency)
    return (ranked["_rank"] < k).reindex(frame.index)


def precision_per_period(frame: pd.DataFrame, k: int, frequency: str) -> pd.Series:
    """Return the precision of the top K of each period.

    Args:
        frame: a ranking frame.
        k: handling capacity per period.
        frequency: pandas period frequency.

    Returns:
        The precision of each period, indexed by period.
    """
    ranked = _ranked(frame, frequency)
    head = ranked.loc[ranked["_rank"] < k]
    return head.groupby("_period", sort=True)["y"].mean().rename("precision")


def precision_at_k(frame: pd.DataFrame, k: int, frequency: str) -> float:
    """Return the mean over periods of the precision of their top K.

    Args:
        frame: a ranking frame.
        k: handling capacity per period.
        frequency: pandas period frequency.

    Returns:
        The Precision@K, or ``nan`` on an empty frame.
    """
    per_period = precision_per_period(frame, k, frequency)
    return float(per_period.mean()) if len(per_period) else float("nan")


def recall_at_k(frame: pd.DataFrame, k: int, frequency: str) -> float:
    """Return the share of all positives captured by the top K of their period.

    Args:
        frame: a ranking frame.
        k: handling capacity per period.
        frequency: pandas period frequency.

    Returns:
        The pooled recall at K, or ``nan`` when the frame holds no positive.
    """
    positives = int(frame["y"].sum())
    if positives == 0:
        return float("nan")
    captured = int(frame.loc[top_k_mask(frame, k, frequency), "y"].sum())
    return captured / positives


def lift(value: float, reference: float) -> float:
    """Return how many times ``value`` exceeds ``reference``.

    Args:
        value: the measure of the scorer under review.
        reference: the measure of the reference ranking.

    Returns:
        The ratio, or ``nan`` when the reference is zero or undefined.
    """
    if not np.isfinite(reference) or reference == 0:
        return float("nan")
    return value / reference


def roc_auc(frame: pd.DataFrame) -> float:
    """Return the ROC-AUC, for information only.

    Args:
        frame: a ranking frame.

    Returns:
        The area under the curve, or ``nan`` when only one class is present.
    """
    if frame["y"].nunique() < _BINARY_CLASSES:
        return float("nan")
    return float(roc_auc_score(frame["y"], frame["score"]))
