"""The three baselines every model must beat, decision D5.

Without a point of comparison a Precision@K means nothing. Each baseline answers
a question a sceptical reader would ask.

Random ranking
    What does a list drawn by chance achieve? Its precision is the base rate.
Revenue ranking
    What does a salesperson achieve without any tool, calling the biggest
    accounts first? This is the baseline that matters commercially, and the lift
    of every model is expressed against it.
Logistic regression
    What does a simple, regularised linear model achieve on the same features?
    If a tree ensemble does not clearly beat it, its cost is not justified.

A scorer receives the training rows and the test rows of one fold and returns one
score per test row. It fits on training rows only, **normalisation included**:
the scaler lives inside the pipeline, so its mean and deviation are learned on
the past alone. Computing them on the whole grid before splitting is one of the
leaks listed in section 3.3 of the data contract.
"""

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

__all__ = [
    "LogisticScorer",
    "RandomScorer",
    "RevenueScorer",
    "Scorer",
    "default_baselines",
]

logger = logging.getLogger(__name__)

#: Classes a classifier needs to learn anything.
_BINARY_CLASSES = 2


class Scorer(Protocol):
    """Anything able to rank the test rows of a fold."""

    name: str

    def fit_score(
        self,
        train_features: pd.DataFrame,
        train_target: pd.Series,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Fit on the training rows and return one score per test row."""
        ...


class RandomScorer:
    """Ranks the test rows by chance, with a seeded generator."""

    name = "random"

    def __init__(self, seed: int) -> None:
        """Initialise the scorer.

        Args:
            seed: seed of the draw, so two runs rank identically.
        """
        self._seed = seed

    def fit_score(
        self,
        train_features: pd.DataFrame,
        train_target: pd.Series,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Return uniform random scores, ignoring every input but the size."""
        del train_features, train_target, test_grid
        return np.random.default_rng(self._seed).random(len(test_features))


class RevenueScorer:
    """Ranks the test rows by monthly revenue, the tool less salesperson."""

    name = "revenue"

    def fit_score(
        self,
        train_features: pd.DataFrame,
        train_target: pd.Series,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Return the revenue of each test row as its score."""
        del train_features, train_target, test_features
        return test_grid["mrr"].to_numpy(dtype="float64")


class LogisticScorer:
    """Regularised logistic regression on standardised features."""

    name = "logistic"

    def __init__(self, regularisation: float = 1.0, max_iter: int = 2000) -> None:
        """Initialise the scorer.

        Args:
            regularisation: inverse strength of the L2 penalty, scikit-learn ``C``.
            max_iter: iteration cap of the solver.
        """
        self._regularisation = regularisation
        self._max_iter = max_iter
        self.pipeline: Pipeline | None = None

    @staticmethod
    def _clean(features: pd.DataFrame) -> np.ndarray:
        """Return the features with infinities neutralised.

        A trend is a ratio of two adjacent windows. A window sum may be negative
        for families whose payload is signed, which can drive the denominator to
        zero. The linear solver refuses infinities, so they become zero here, a
        value the scaler then centres like any other.
        """
        values = features.to_numpy(dtype="float64", copy=True)
        values[~np.isfinite(values)] = 0.0
        return values

    def fit_score(
        self,
        train_features: pd.DataFrame,
        train_target: pd.Series,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Fit on the training rows and return the probability of churn."""
        del test_grid
        if train_target.nunique() < _BINARY_CLASSES:
            logger.warning("training fold holds a single class, constant scores returned")
            self.pipeline = None
            return np.zeros(len(test_features))

        self.pipeline = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=self._regularisation, max_iter=self._max_iter),
        )
        self.pipeline.fit(self._clean(train_features), train_target.to_numpy())
        return self.pipeline.predict_proba(self._clean(test_features))[:, 1]


def default_baselines(seed: int) -> list[Scorer]:
    """Return the three baselines, in the order they are reported."""
    return [RandomScorer(seed), RevenueScorer(), LogisticScorer()]
