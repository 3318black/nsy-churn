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

A scorer receives the training rows of one fold, whole, and the test rows
without their target, and returns one score per test row. It fits on training
rows only, **normalisation included**: the scaler lives inside the pipeline, so
its mean and deviation are learned on the past alone. Computing them on the whole
grid before splitting is one of the leaks listed in section 3.3 of the data
contract.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from typing import Protocol

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from churn.config import FeatureSource
from churn.evaluation.selection import Selection, SelectionSettings, select_candidate
from churn.features.build import TrainingSet
from churn.features.catalog import select_families

__all__ = [
    "LogisticScorer",
    "RandomScorer",
    "RevenueScorer",
    "Scorer",
    "TunedLogisticScorer",
    "default_baselines",
    "signed_log1p",
]

logger = logging.getLogger(__name__)

#: Classes a classifier needs to learn anything.
_BINARY_CLASSES = 2

#: Iteration cap of the tuned regression. Compressed and scaled columns converge
#: quickly; the cap only guards against a pathological fold.
_TUNED_MAX_ITER = 2000


class Scorer(Protocol):
    """Anything able to rank the test rows of a fold."""

    name: str

    def fit_score(
        self,
        train: TrainingSet,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Fit on the training rows and return one score per test row.

        Args:
            train: grid, target and features of the training rows. A scorer that
                tunes itself cuts its inner split on these dates, never on the
                test ones.
            test_features: features of the test rows.
            test_grid: ``T0``, ``client_id`` and ``mrr`` of the test rows. The
                target is removed before it reaches any scorer.
        """
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
        train: TrainingSet,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Return uniform random scores, ignoring every input but the size."""
        del train, test_grid
        return np.random.default_rng(self._seed).random(len(test_features))


class RevenueScorer:
    """Ranks the test rows by monthly revenue, the tool less salesperson."""

    name = "revenue"

    def fit_score(
        self,
        train: TrainingSet,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Return the revenue in force at ``T0`` of each test row as its score."""
        del train, test_features
        return test_grid["mrr"].to_numpy(dtype="float64")


class LogisticScorer:
    """Regularised logistic regression on standardised features."""

    def __init__(
        self,
        regularisation: float = 1.0,
        max_iter: int = 2000,
        families: Collection[FeatureSource] | None = None,
        name: str = "logistic",
    ) -> None:
        """Initialise the scorer.

        Args:
            regularisation: inverse strength of the L2 penalty, scikit-learn ``C``.
            max_iter: iteration cap of the solver.
            families: feature families to learn from, all of them when ``None``.
            name: name the scorer is reported under.
        """
        self._regularisation = regularisation
        self._max_iter = max_iter
        self._families = families
        self.name = name
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

    def _scoped(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return the features of the families this scorer learns from."""
        return features if self._families is None else select_families(features, self._families)

    def fit_score(
        self,
        train: TrainingSet,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Fit on the training rows and return the probability of churn."""
        del test_grid
        if train.target.nunique() < _BINARY_CLASSES:
            logger.warning("training fold holds a single class, constant scores returned")
            self.pipeline = None
            return np.zeros(len(test_features))

        self.pipeline = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=self._regularisation, max_iter=self._max_iter),
        )
        self.pipeline.fit(self._clean(self._scoped(train.features)), train.target.to_numpy())
        return self.pipeline.predict_proba(self._clean(self._scoped(test_features)))[:, 1]


def signed_log1p(values: np.ndarray) -> np.ndarray:
    """Compress heavy tailed values, keeping their sign.

    A count of listening days runs from zero to ninety, a sum of invoiced amounts
    into the thousands, and a few accounts sit far above the rest. A linear model
    reads such columns badly: the extreme accounts pull every weight. The
    logarithm brings them back to a comparable scale; the sign keeps the few
    signed families, such as payment delays, meaningful.
    """
    return np.sign(values) * np.log1p(np.abs(values))


class TunedLogisticScorer:
    """Logistic regression made a fair opponent, decision D23.

    The plain baseline standardises raw columns and keeps the default penalty.
    This one compresses heavy tails first, then chooses its penalty on the same
    inner chronological split the boosted trees are tuned on. If the trees still
    beat it clearly, the gain cannot be blamed on a weak baseline.
    """

    def __init__(
        self,
        regularisations: Sequence[float],
        settings: SelectionSettings,
        families: Collection[FeatureSource] | None = None,
        name: str = "logistic_tuned",
    ) -> None:
        """Initialise the scorer.

        Args:
            regularisations: inverse penalty strengths to choose from, ``C``.
            settings: what the inner selection needs.
            families: feature families to learn from, all of them when ``None``.
            name: name the scorer is reported under.
        """
        if not regularisations:
            message = "at least one regularisation strength is required"
            raise ValueError(message)
        self._regularisations = tuple(regularisations)
        self._settings = settings
        self._families = families
        self.name = name
        self.selections: list[Selection[float]] = []
        self.pipeline: Pipeline | None = None

    @staticmethod
    def build_pipeline(regularisation: float) -> Pipeline:
        """Return the unfitted pipeline: compression, scaling, regression."""
        return make_pipeline(
            FunctionTransformer(signed_log1p),
            StandardScaler(),
            LogisticRegression(C=regularisation, max_iter=_TUNED_MAX_ITER),
        )

    def _scoped(self, features: pd.DataFrame) -> pd.DataFrame:
        """Return the features of the families this scorer learns from."""
        return features if self._families is None else select_families(features, self._families)

    def fit_score(
        self,
        train: TrainingSet,
        test_features: pd.DataFrame,
        test_grid: pd.DataFrame,
    ) -> np.ndarray:
        """Choose the penalty on the training rows, fit, and score the test rows."""
        del test_grid
        if train.target.nunique() < _BINARY_CLASSES:
            logger.warning("training fold holds a single class, constant scores returned")
            self.pipeline = None
            return np.zeros(len(test_features))

        train = train._replace(features=self._scoped(train.features))
        test_features = self._scoped(test_features)

        def score(
            regularisation: float, inner: TrainingSet, validation: pd.DataFrame
        ) -> np.ndarray:
            pipeline = self.build_pipeline(regularisation)
            pipeline.fit(LogisticScorer._clean(inner.features), inner.target.to_numpy())
            return pipeline.predict_proba(LogisticScorer._clean(validation))[:, 1]

        selection = select_candidate(
            train,
            self._regularisations,
            self._settings,
            score,
            lambda regularisation: {"regularisation": regularisation},
        )
        self.selections.append(selection)
        self.pipeline = self.build_pipeline(selection.params)
        self.pipeline.fit(LogisticScorer._clean(train.features), train.target.to_numpy())
        return self.pipeline.predict_proba(LogisticScorer._clean(test_features))[:, 1]


def default_baselines(seed: int) -> list[Scorer]:
    """Return the three baselines, in the order they are reported."""
    return [RandomScorer(seed), RevenueScorer(), LogisticScorer()]
