"""Scoring of one date: ranks, deciles, actionable factors and batch identity.

Four choices shape the export, each recorded in the decisions register.

Actionable factors only, decision D19
    A factor with no lever, such as the account age or its revenue, still weighs
    in the score but never takes a factor slot. A salesperson can do nothing with
    "account age", and a slot spent on it hides a reason they could act on.
A deterministic batch identity, decision D20
    ``batch_run_id`` is derived from the model version, the scoring date and a
    digest of the scored inputs. A random identifier would make two runs on the
    same data produce two different files, which the acceptance criteria forbid.
    The same inputs yield the same identifier; any change yields another one.
Rank and decile, never a percentage, decision D6
    The raw score is kept in a technical column. The business reads a rank and
    a decile.
Contributions travel with the rows, decision D21
    The interface shows why an account ranks where it does. It may not recompute
    anything, so every contribution summed by origin variable is exported next to
    the rows, with the significance threshold that filtered the factors.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from churn.config import FeatureMappingEntry
from churn.features.build import ScoringSet
from churn.models.explain import aggregate_by_origin, check_mapping, factor_labels, top_factors
from churn.models.registry import TrainedModel, training_fingerprint
from churn.pipeline.schemas import (
    CONTRIBUTION_COLUMNS,
    EXPORT_COLUMNS,
    FACTOR_COLUMNS,
    validate_export,
)

__all__ = [
    "BATCH_NAMESPACE",
    "ExportSettings",
    "ScoringBatch",
    "actionable_origins",
    "batch_run_id",
    "risk_deciles",
    "score_accounts",
]

#: Namespace every batch identifier is derived in.
BATCH_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/3318black/nsy-churn/scoring")

#: Number of risk deciles.
_DECILES = 10


@dataclass(frozen=True, slots=True)
class ExportSettings:
    """What the export needs from the configuration.

    Attributes:
        k: weekly handling capacity, which sets ``is_top_k``.
        top_factors: number of factor columns, fixed at three by the contract.
        max_label_length: longest label a factor may carry.
        source_label: label of the data source.
        is_synthetic: whether the data is simulated, decision D2.
    """

    k: int
    top_factors: int
    max_label_length: int
    source_label: str
    is_synthetic: bool


@dataclass(frozen=True, slots=True)
class ScoringBatch:
    """One scored date, ready to be written.

    Attributes:
        rows: the exported rows, in contract order and output sort.
        contributions: one row per account and origin variable, decision D21.
        batch_run_id: identifier of the run, written on every row.
        date_scoring: the scoring date.
        model_version: version of the model, written on every row.
        significance_threshold: threshold the factors were filtered with.
        source_label: label of the data source.
        is_synthetic: whether the data is simulated.
    """

    rows: pd.DataFrame
    contributions: pd.DataFrame
    batch_run_id: uuid.UUID
    date_scoring: date
    model_version: str
    significance_threshold: float
    source_label: str
    is_synthetic: bool


def actionable_origins(mapping: Mapping[str, FeatureMappingEntry]) -> frozenset[str]:
    """Return the origin variables whose label carries an action, decision D19."""
    return frozenset(origin for origin, entry in mapping.items() if entry.action.strip())


def batch_run_id(model_version: str, scoring_date: date, inputs_digest: str) -> uuid.UUID:
    """Derive the identifier of a run from what the run depends on.

    Args:
        model_version: version of the model used.
        scoring_date: the scoring date.
        inputs_digest: digest of the scored rows and their features.

    Returns:
        The same identifier for the same inputs, another one otherwise.
    """
    name = f"{model_version}|{scoring_date.isoformat()}|{inputs_digest}"
    return uuid.uuid5(BATCH_NAMESPACE, name)


def risk_deciles(ranks: np.ndarray, total: int) -> np.ndarray:
    """Return the risk decile of each rank, 1 holding the highest scores.

    Deciles differ in size by one row at most.

    Args:
        ranks: ranks starting at 1.
        total: number of scored rows.

    Returns:
        The decile of each rank, from 1 to 10.
    """
    if total == 0:
        return np.array([], dtype="int64")
    return np.clip(np.ceil(ranks * _DECILES / total), 1, _DECILES).astype("int64")


def _empty_frame(columns: tuple[str, ...]) -> pd.DataFrame:
    """Return a frame without any row, carrying the given columns."""
    return pd.DataFrame({column: pd.Series([], dtype="object") for column in columns})


def _contribution_rows(
    aggregated: pd.DataFrame,
    client_ids: np.ndarray,
    mapping: Mapping[str, FeatureMappingEntry],
    actionable: Collection[str],
) -> pd.DataFrame:
    """Return the contributions in long form, one row per account and origin.

    Args:
        aggregated: contributions summed by origin, one row per scored account.
        client_ids: identifier of each row of ``aggregated``.
        mapping: the business mapping, which names every origin.
        actionable: the origins that may take a factor slot.

    Returns:
        The contributions, sorted by account, then by decreasing contribution.
    """
    origins = list(aggregated.columns)
    check_mapping(origins, mapping)
    labels = [f"[{mapping[origin].source.value}] {mapping[origin].label}" for origin in origins]
    rows, width = aggregated.shape
    frame = pd.DataFrame(
        {
            "client_id": np.repeat(client_ids, width),
            "variable_origine": np.tile(np.asarray(origins, dtype=object), rows),
            "libelle": np.tile(np.asarray(labels, dtype=object), rows),
            "contribution": aggregated.to_numpy(dtype="float64").ravel(),
            "actionnable": np.tile(np.asarray([o in actionable for o in origins]), rows),
        }
    )
    return frame.sort_values(
        ["client_id", "contribution", "variable_origine"],
        ascending=[True, False, True],
        kind="stable",
        ignore_index=True,
    ).loc[:, list(CONTRIBUTION_COLUMNS)]


def score_accounts(
    scoring: ScoringSet,
    model: TrainedModel,
    mapping: Mapping[str, FeatureMappingEntry],
    settings: ExportSettings,
) -> ScoringBatch:
    """Score the accounts of one date and shape the export.

    Args:
        scoring: the accounts to score and their features.
        model: the saved model.
        mapping: the business mapping of the factors.
        settings: what the export needs from the configuration.

    Returns:
        The batch, checked against the output contract.

    Raises:
        ValueError: when the configured number of factors differs from the
            contract, or when the batch breaches it.
    """
    if settings.top_factors != len(FACTOR_COLUMNS):
        message = (
            f"business.top_factors is {settings.top_factors}, but the output contract "
            f"carries exactly {len(FACTOR_COLUMNS)} factor columns"
        )
        raise ValueError(message)

    day = scoring.date.date()
    version = model.metadata.model_version
    threshold = model.metadata.significance_threshold
    grid = scoring.grid
    if grid.empty:
        rows = _empty_frame(EXPORT_COLUMNS)
        contributions = _empty_frame(CONTRIBUTION_COLUMNS)
        run_id = batch_run_id(version, day, "empty")
    else:
        scores = model.score(scoring.features).astype("float64")
        aggregated = aggregate_by_origin(model.contributions(scoring.features))
        # Decision D19: only origins a salesperson can act on compete for a slot.
        actionable = actionable_origins(mapping)
        eligible = aggregated.loc[
            :, [origin for origin in aggregated.columns if origin in actionable]
        ]
        factors = factor_labels(top_factors(eligible, threshold, settings.top_factors), mapping)
        ranking = (
            pd.DataFrame(
                {
                    "client_id": grid["client_id"].to_numpy(),
                    "mrr": grid["mrr"].to_numpy(dtype="float64"),
                    "score_brut_technique": scores,
                },
                index=grid.index,
            )
            .join(factors)
            .sort_values(
                ["score_brut_technique", "mrr", "client_id"],
                ascending=[False, False, True],
                kind="stable",
                ignore_index=True,
            )
        )
        ranks = np.arange(1, len(ranking) + 1)
        digest = training_fingerprint(scoring.features, grid["client_id"])
        run_id = batch_run_id(version, day, digest)
        rows = ranking.assign(
            batch_run_id=str(run_id),
            date_scoring=day,
            rang_priorite=ranks,
            decile_risque=risk_deciles(ranks, len(ranking)),
            is_top_k=ranks <= settings.k,
            model_version=version,
        ).loc[:, list(EXPORT_COLUMNS)]
        contributions = _contribution_rows(
            aggregated, grid.loc[aggregated.index, "client_id"].to_numpy(), mapping, actionable
        )

    validate_export(rows, settings.max_label_length)
    return ScoringBatch(
        rows=rows,
        contributions=contributions,
        batch_run_id=run_id,
        date_scoring=day,
        model_version=version,
        significance_threshold=threshold,
        source_label=settings.source_label,
        is_synthetic=settings.is_synthetic,
    )
