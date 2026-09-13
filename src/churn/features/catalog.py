"""Where a feature column comes from.

Two questions are answered here, and only here, so that no module parses a column
name on its own.

Origin
    The business variable a column was derived from, before any encoding. The
    windows of one event type are several columns but a single variable.
    Decision D7 sums the contributions at this level before extracting the three
    factors: without it, one reason would be printed three times under three
    windows, and a salesperson would read three reasons where there is one.
Family
    The source of the signal, ``PRODUCT``, ``FINANCE``, ``SUPPORT``,
    ``COMMERCIAL`` or ``GENERAL``. It prefixes the business label, and it lets a
    measurement keep or drop a whole family to isolate what that family adds.
"""

from __future__ import annotations

import re
from collections.abc import Collection

import pandas as pd

from churn.config import FeatureSource
from churn.data.schemas import EVENT_FAMILIES, EventType
from churn.features.windows import WINDOW_SUFFIX, AggregateKind

__all__ = ["INDICATOR_SEPARATOR", "TREND_PREFIX", "family_of", "origin_of", "select_families"]

#: Separator between a variable and its modality in an indicator column, as in
#: ``type_contrat=mensuel``.
INDICATOR_SEPARATOR = "="

#: Prefix of the trend features, kept on the origin: a level and a break are two
#: different reasons to call.
TREND_PREFIX = "trend_"

_WINDOW_PATTERN = re.compile(
    rf"^(?P<trend>{TREND_PREFIX})?(?:{AggregateKind.COUNT}|{AggregateKind.SUM})_"
    rf"(?P<event>[a-z_]+?)_\d+{WINDOW_SUFFIX}$"
)


def origin_of(column: str) -> str:
    """Return the origin variable of a feature column.

    Three shapes are recognised. A window feature such as ``count_connexion_30j``
    comes from its event type, ``connexion``; its trend ``trend_sum_connexion_7j``
    comes from ``trend_connexion``. An indicator such as ``type_contrat=mensuel``
    comes from the variable before the separator. Any other column is its own
    origin, like ``anciennete_jours``.

    Args:
        column: name of the feature column.

    Returns:
        The name of the origin variable.
    """
    variable = column.split(INDICATOR_SEPARATOR, 1)[0]
    match = _WINDOW_PATTERN.match(variable)
    if match is None:
        return variable
    return f"{match['trend'] or ''}{match['event']}"


def family_of(column: str) -> FeatureSource:
    """Return the business family of a feature column.

    Args:
        column: name of the feature column.

    Returns:
        The family of its event type, or ``GENERAL`` for a structural column.
    """
    origin = origin_of(column).removeprefix(TREND_PREFIX)
    try:
        event_type = EventType(origin)
    except ValueError:
        return FeatureSource.GENERAL
    return EVENT_FAMILIES[event_type]


def select_families(features: pd.DataFrame, families: Collection[FeatureSource]) -> pd.DataFrame:
    """Keep the feature columns of the given families only.

    Args:
        features: the feature matrix.
        families: families to keep. ``GENERAL`` must be named to be kept.

    Returns:
        The restricted matrix, columns in their original order.
    """
    kept = [column for column in features.columns if family_of(column) in families]
    return features.loc[:, kept]
