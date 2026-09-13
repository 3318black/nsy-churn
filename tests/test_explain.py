"""Tests of the feature catalog and of the local explanation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from churn.config import AppConfig, FeatureMappingEntry, FeatureSource, load_feature_mapping
from churn.data.schemas import STATE_EVENT_TYPES, EventType
from churn.features.catalog import family_of, origin_of, select_families
from churn.models.explain import (
    aggregate_by_origin,
    check_mapping,
    factor_labels,
    feature_contributions,
    significance_threshold,
    top_factors,
)


@pytest.fixture(scope="module")
def mapping(config: AppConfig) -> dict[str, FeatureMappingEntry]:
    """The business mapping of the repository."""
    return load_feature_mapping(config.paths.feature_mapping)


def test_window_columns_resolve_to_their_event_type() -> None:
    """Three windows of one event type are one variable, decision D7."""
    assert origin_of("count_connexion_7j") == "connexion"
    assert origin_of("sum_usage_module_cle_90j") == "usage_module_cle"
    assert origin_of("trend_count_connexion_30j") == "trend_connexion"
    assert origin_of("trend_sum_desactivation_renouvellement_7j") == (
        "trend_desactivation_renouvellement"
    )


def test_structural_and_indicator_columns_resolve_to_their_variable() -> None:
    """A structural column is its own origin, an indicator its variable."""
    assert origin_of("anciennete_jours") == "anciennete_jours"
    assert origin_of("mrr") == "mrr"
    assert origin_of("type_contrat=mensuel") == "type_contrat"


def test_families_follow_the_nomenclature() -> None:
    """The family prefixes the label and drives the ablation."""
    assert family_of("count_facture_emise_7j") is FeatureSource.FINANCE
    assert family_of("trend_sum_taux_completion_30j") is FeatureSource.PRODUCT
    assert family_of("mrr") is FeatureSource.GENERAL


def test_selecting_families_keeps_general_only_when_named() -> None:
    """Structural columns are a family like any other."""
    features = pd.DataFrame(columns=["count_connexion_7j", "count_facture_emise_7j", "mrr"])
    assert list(select_families(features, {FeatureSource.FINANCE}).columns) == [
        "count_facture_emise_7j"
    ]
    finance = select_families(features, {FeatureSource.FINANCE, FeatureSource.GENERAL})
    assert list(finance.columns) == ["count_facture_emise_7j", "mrr"]


def test_contributions_of_an_indicator_variable_are_summed() -> None:
    """Criterion 2 of lot 5: modalities and windows of one variable add up."""
    contributions = pd.DataFrame(
        {
            "type_contrat=mensuel": [0.2, -0.1],
            "type_contrat=annuel": [0.3, 0.0],
            "count_connexion_7j": [0.1, 0.4],
            "sum_connexion_30j": [0.05, -0.5],
            "mrr": [0.0, 0.2],
        }
    )
    aggregated = aggregate_by_origin(contributions)
    assert list(aggregated.columns) == ["connexion", "mrr", "type_contrat"]
    assert aggregated.loc[0, "type_contrat"] == pytest.approx(0.5)
    assert aggregated.loc[1, "type_contrat"] == pytest.approx(-0.1)
    assert aggregated.loc[1, "connexion"] == pytest.approx(-0.1)


def test_the_bias_column_is_dropped_from_the_contributions() -> None:
    """Criterion 3 of lot 5: the last column of pred_contribs is the bias."""
    rng = np.random.default_rng(0)
    features = pd.DataFrame(rng.normal(size=(500, 3)), columns=["a", "b", "c"])
    target = (features["a"] + rng.normal(scale=0.5, size=500) > 0).astype(int)
    classifier = xgb.XGBClassifier(n_estimators=20, max_depth=3, random_state=1)
    classifier.fit(features, target)

    contributions = feature_contributions(classifier, features)
    booster = classifier.get_booster()
    raw = booster.predict(xgb.DMatrix(features), pred_contribs=True)
    margin = booster.predict(xgb.DMatrix(features), output_margin=True)

    assert list(contributions.columns) == ["a", "b", "c"]
    bias = raw[:, -1]
    assert np.allclose(bias, bias[0]), "the dropped column must be the constant bias"
    assert np.allclose(contributions.sum(axis=1) + bias, margin, atol=1e-5)


def test_only_positive_significant_contributions_become_factors() -> None:
    """A contribution lowering the risk, or below the threshold, is not a reason."""
    aggregated = pd.DataFrame({"a": [0.9, -0.2], "b": [0.5, 0.01], "c": [0.1, -0.3], "d": [0.7, 0]})
    factors = top_factors(aggregated, threshold=0.2, count=3)
    assert list(factors.columns) == ["facteur_risque_1", "facteur_risque_2", "facteur_risque_3"]
    assert list(factors.iloc[0]) == ["a", "d", "b"]
    assert list(factors.iloc[1]) == ["", "", ""]


def test_an_account_without_significant_factor_gets_empty_labels(
    mapping: dict[str, FeatureMappingEntry],
) -> None:
    """Criterion 6 of lot 5: an invented reason is worse than no reason."""
    aggregated = pd.DataFrame({"connexion": [0.05], "mrr": [0.01]})
    labels = factor_labels(top_factors(aggregated, threshold=0.5, count=3), mapping)
    assert (labels.to_numpy() == "").all()


def test_ties_are_broken_by_origin_name() -> None:
    """Two runs on the same data print the same factors."""
    aggregated = pd.DataFrame({"b": [0.5], "a": [0.5]})
    assert list(top_factors(aggregated, threshold=0.0, count=2).iloc[0]) == ["a", "b"]


def test_fewer_origins_than_factors_pads_with_empty_cells() -> None:
    """The output keeps its shape whatever the number of variables."""
    factors = top_factors(pd.DataFrame({"a": [0.5], "b": [0.4]}), threshold=0.0, count=3)
    assert list(factors.iloc[0]) == ["a", "b", ""]


def test_labels_are_prefixed_by_their_source(mapping: dict[str, FeatureMappingEntry]) -> None:
    """The salesperson reads the family before the reason."""
    factors = pd.DataFrame({"facteur_risque_1": ["connexion"], "facteur_risque_2": [""]})
    labels = factor_labels(factors, mapping)
    assert labels.iloc[0, 0] == "[PRODUCT] Fréquence d'usage"
    assert labels.iloc[0, 1] == ""


def test_an_origin_without_label_fails_loudly(mapping: dict[str, FeatureMappingEntry]) -> None:
    """A factor is never printed under its technical name."""
    with pytest.raises(ValueError, match="inconnue"):
        check_mapping(["connexion", "inconnue"], mapping)


def test_the_mapping_covers_every_origin_the_pipeline_can_build(
    mapping: dict[str, FeatureMappingEntry],
) -> None:
    """Every flow of the nomenclature, its trend, and the structural columns."""
    flows = [member.value for member in EventType if member not in STATE_EVENT_TYPES]
    expected = {*flows, *(f"trend_{flow}" for flow in flows), "anciennete_jours", "mrr"}
    check_mapping(expected, mapping)


def test_the_threshold_is_a_quantile_of_absolute_contributions() -> None:
    """Negative contributions count by their size, D7."""
    aggregated = pd.DataFrame({"a": [-4.0, 1.0], "b": [2.0, 3.0]})
    assert significance_threshold(aggregated, 0.5) == pytest.approx(2.5)
