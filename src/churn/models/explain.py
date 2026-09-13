"""Local explanation: the risk factors of each account, decisions D7 and D12.

A score tells a salesperson whom to call. It does not tell what to say. This
module turns the contributions of the model into at most three business factors
per account, and it refuses to invent one.

Native contributions
    XGBoost computes the exact TreeSHAP contributions itself, through
    ``pred_contribs``. The ``shap`` library gives the very same values, measured
    to the bit in decision D12, at the cost of a compiler shipped in production.
    The returned array carries one extra column, the bias, identical on every row
    and owned by no variable. It is dropped here, explicitly.
Aggregation by origin
    Contributions are summed per origin variable before anything is ranked. The
    three windows of one event type are three columns but one reason. Decision D7.
Significance
    Only positive contributions push the risk up, and only those above a
    threshold are shown. The threshold is a quantile of the absolute aggregated
    contributions, computed at training time and serialised with the model, never
    written in the code. A row with nothing above it gets empty factors: an
    invented reason is worse than no reason.

**Labels name a signal, not its direction.** A positive contribution says that
the value of a variable pushes the risk up, not whether that value is high or
low. Printing "drop in usage" would be a guess, so the labels stay neutral.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd
import xgboost as xgb

from churn.config import FeatureMappingEntry
from churn.features.catalog import origin_of

__all__ = [
    "FACTOR_COLUMN_PREFIX",
    "aggregate_by_origin",
    "check_mapping",
    "factor_labels",
    "feature_contributions",
    "significance_threshold",
    "top_factors",
]

#: Prefix of the factor columns, as named by the output contract.
FACTOR_COLUMN_PREFIX = "facteur_risque_"


def feature_contributions(classifier: xgb.XGBClassifier, features: pd.DataFrame) -> pd.DataFrame:
    """Return the native contribution of every feature, bias excluded.

    Args:
        classifier: a fitted classifier.
        features: the features, already prepared for the model.

    Returns:
        One column per feature, one row per input row. Each row sums, with the
        bias, to the raw margin of the model.
    """
    raw = classifier.get_booster().predict(xgb.DMatrix(features), pred_contribs=True)
    # The last column is the bias: shared by every row, owned by no variable.
    # Ranking it as a factor would print the same reason for every account.
    return pd.DataFrame(raw[:, :-1], index=features.index, columns=features.columns)


def aggregate_by_origin(contributions: pd.DataFrame) -> pd.DataFrame:
    """Sum the contributions of the columns that share an origin variable.

    Args:
        contributions: one column per feature.

    Returns:
        One column per origin variable, in alphabetical order.
    """
    origins = np.array([origin_of(column) for column in contributions.columns])
    names = sorted(set(origins))
    values = contributions.to_numpy(dtype="float64")
    summed = np.column_stack([values[:, origins == name].sum(axis=1) for name in names])
    return pd.DataFrame(summed, index=contributions.index, columns=names)


def significance_threshold(aggregated: pd.DataFrame, quantile: float) -> float:
    """Return the quantile of the absolute aggregated contributions.

    Args:
        aggregated: contributions summed by origin, on training rows.
        quantile: quantile to take, from ``model.significance_quantile``.

    Returns:
        The threshold a contribution must exceed to be shown.

    Raises:
        ValueError: when there is no contribution to compute it on.
    """
    values = np.abs(aggregated.to_numpy(dtype="float64"))
    if values.size == 0:
        message = "no contribution to compute a significance threshold on"
        raise ValueError(message)
    return float(np.quantile(values, quantile))


def top_factors(aggregated: pd.DataFrame, threshold: float, count: int) -> pd.DataFrame:
    """Return the origins of the strongest positive contributions of each row.

    Args:
        aggregated: contributions summed by origin.
        threshold: significance threshold serialised with the model.
        count: number of factors per row, from ``business.top_factors``.

    Returns:
        Columns ``facteur_risque_1`` onwards, holding an origin name or an empty
        string when no significant factor remains.
    """
    columns = [f"{FACTOR_COLUMN_PREFIX}{rank}" for rank in range(1, count + 1)]
    factors = pd.DataFrame("", index=aggregated.index, columns=columns, dtype="str")
    if aggregated.empty or aggregated.shape[1] == 0:
        return factors

    ordered = aggregated.reindex(columns=sorted(aggregated.columns))
    names = np.asarray(ordered.columns, dtype=object)
    values = ordered.to_numpy(dtype="float64")
    # A stable sort on the negated values: ties keep the alphabetical order of
    # the origins, so two runs print the same factors.
    order = np.argsort(-values, axis=1, kind="stable")[:, :count]
    picked = np.take_along_axis(values, order, axis=1)
    kept = (picked > 0.0) & (picked > threshold)
    labels = np.where(kept, names[order], "")
    for position in range(labels.shape[1]):
        factors[columns[position]] = labels[:, position].astype(str)
    return factors


def check_mapping(origins: Iterable[str], mapping: Mapping[str, FeatureMappingEntry]) -> None:
    """Fail when an origin variable has no business label.

    Args:
        origins: origin variables the model may print.
        mapping: the business mapping.

    Raises:
        ValueError: naming every origin without a label. A factor is never shown
            under its technical name.
    """
    missing = sorted(set(origins) - set(mapping))
    if missing:
        message = (
            f"no business label for the origin variables {missing}: add them to "
            f"config/feature_mapping.yaml"
        )
        raise ValueError(message)


def factor_labels(
    factors: pd.DataFrame, mapping: Mapping[str, FeatureMappingEntry]
) -> pd.DataFrame:
    """Replace origin names by their business label, prefixed by their source.

    Args:
        factors: the output of :func:`top_factors`.
        mapping: the business mapping.

    Returns:
        The same frame, each origin rendered as ``[SOURCE] label``, empty cells
        left empty.
    """
    present = {value for value in factors.to_numpy().ravel() if value}
    check_mapping(present, mapping)
    rendered = {
        origin: f"[{entry.source.value}] {entry.label}" for origin, entry in mapping.items()
    }
    rendered[""] = ""
    return factors.apply(lambda column: column.map(rendered))
