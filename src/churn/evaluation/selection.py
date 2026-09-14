"""Choice of a model setting on the training rows alone, decisions D16 and D23.

Any model with settings to choose, the boosted trees as much as the tuned
logistic baseline, goes through the very same selection. Two rules hold.

The test period is never seen
    The training dates are cut in two chronological halves, with the embargo and
    the purge of the outer protocol. Each candidate fits on the first half and is
    measured by its Precision@K on the second. Choosing on the test folds would
    turn the evaluation into a selection, and the reported figure into the best of
    several draws.
A failure is said, not hidden
    When the inner split leaves nothing to measure, the first candidate is kept
    and the reason is logged and returned with the selection.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from churn.evaluation.metrics import precision_at_k
from churn.evaluation.splitting import temporal_folds
from churn.features.build import TrainingSet

__all__ = ["Selection", "SelectionSettings", "select_candidate"]

logger = logging.getLogger(__name__)

#: Classes a classifier needs to learn anything.
_BINARY_CLASSES = 2


@dataclass(frozen=True, slots=True)
class SelectionSettings:
    """What the inner selection needs to measure a candidate.

    Attributes:
        k: handling capacity per period.
        frequency: scoring period frequency.
        horizon_days: days the target resolves over.
        embargo_days: days kept empty between inner training and validation.
        seed: seed of every fit.
    """

    k: int
    frequency: str
    horizon_days: int
    embargo_days: int
    seed: int


@dataclass(frozen=True, slots=True)
class Selection[Candidate]:
    """Outcome of one selection.

    Attributes:
        params: the chosen candidate.
        scores: Precision@K of each candidate on the inner validation.
        fallback_reason: why no measure could be taken, empty when one was.
    """

    params: Candidate
    scores: pd.DataFrame
    fallback_reason: str


def _fallback[Candidate](candidates: Sequence[Candidate], reason: str) -> Selection[Candidate]:
    """Return the first candidate, saying loudly why nothing was measured."""
    logger.warning("hyperparameter selection skipped", extra={"reason": reason})
    return Selection(params=candidates[0], scores=pd.DataFrame(), fallback_reason=reason)


def select_candidate[Candidate](
    training: TrainingSet,
    candidates: Sequence[Candidate],
    settings: SelectionSettings,
    score: Callable[[Candidate, TrainingSet, pd.DataFrame], np.ndarray],
    describe: Callable[[Candidate], Mapping[str, object]],
) -> Selection[Candidate]:
    """Choose a candidate on an inner chronological split of the training rows.

    Args:
        training: grid, target and features of the training rows only.
        candidates: the settings to compare. Ties go to the earlier one.
        settings: what the measurement needs.
        score: fits a candidate on the inner training rows and returns one score
            per row of the validation features it receives.
        describe: the columns a candidate is reported under.

    Returns:
        The chosen candidate and the measure of every candidate.
    """
    if not candidates:
        message = "at least one candidate is required"
        raise ValueError(message)
    try:
        folds = temporal_folds(
            training.grid["T0"],
            n_splits=1,
            horizon_days=settings.horizon_days,
            embargo_days=settings.embargo_days,
        )
    except ValueError as error:
        return _fallback(candidates, str(error))
    if not folds:
        return _fallback(candidates, "the inner split leaves no training row")

    fold = folds[0]
    inner = TrainingSet(
        grid=training.grid.iloc[fold.train_index],
        target=training.target.iloc[fold.train_index],
        features=training.features.iloc[fold.train_index],
    )
    validation = training.grid.iloc[fold.test_index]
    if inner.target.nunique() < _BINARY_CLASSES or validation["y"].sum() == 0:
        return _fallback(candidates, "the inner split holds a single class")

    validation_features = training.features.iloc[fold.test_index]
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        ranking = validation[["T0", "client_id", "mrr", "y"]].assign(
            score=score(candidate, inner, validation_features)
        )
        measure = precision_at_k(ranking, settings.k, settings.frequency)
        rows.append({**describe(candidate), "precision_at_k": measure})

    scores = pd.DataFrame(rows)
    best = int(np.argmax(scores["precision_at_k"].fillna(-1.0).to_numpy()))
    return Selection(params=candidates[best], scores=scores, fallback_reason="")
