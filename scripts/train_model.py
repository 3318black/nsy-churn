"""Evaluate the model against the baselines, then train, save and explain it.

    uv run python scripts/train_model.py --source kkbox
    uv run python scripts/train_model.py --source synthetic --accounts 1500

Every ranking goes through the very same folds, periods and K. Two comparisons
answer two different questions.

Model gain
    What do the trees add on the same features? The logistic regression and the
    gradient boosted model, both restricted to the financial family.
Data gain
    What do the listening logs add? The same model with and without the product
    family.

Then the final model is trained on the whole grid, saved with its metadata,
reloaded, and used to explain the last observation date as the Monday list would.

No network access. The KKBox source reads the Parquet tables written by
``scripts/download_kkbox.py``.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn.config import AppConfig, FeatureSource, load_config, load_feature_mapping
from churn.data.sources import ParquetDataSource, SourceDescription
from churn.data.synthetic import generate_dataset
from churn.evaluation.baselines import (
    LogisticScorer,
    RandomScorer,
    RevenueScorer,
    Scorer,
    TunedLogisticScorer,
)
from churn.evaluation.protocol import evaluate_scorers, summarise
from churn.evaluation.report import source_banner, write_evaluation_report
from churn.evaluation.splitting import temporal_folds
from churn.features.build import GridSpec, TrainingSet, build_training_set
from churn.models.explain import (
    FACTOR_COLUMN_PREFIX,
    aggregate_by_origin,
    factor_labels,
    top_factors,
)
from churn.models.registry import load_model, save_model
from churn.models.train import (
    ModelIdentity,
    SelectionSettings,
    TrainingSettings,
    XGBoostScorer,
    param_candidates,
    train_model,
)

logger = logging.getLogger("train_model")

#: The financial family and the structural columns, which is all the lot 4
#: baselines could learn from before the listening logs were extracted.
FINANCE_ONLY = frozenset({FeatureSource.FINANCE, FeatureSource.GENERAL})


def _load_training(
    config: AppConfig, description: SourceDescription, accounts: int | None
) -> TrainingSet:
    """Load the source and build the grid, its target and its features."""
    resolution = config.features.datetime_resolution
    started = time.monotonic()
    if description.key == "synthetic":
        synthetic = config.sources.synthetic
        if accounts:
            synthetic = synthetic.model_copy(update={"n_accounts": accounts})
        dataset = generate_dataset(
            synthetic, seed=config.project.random_seed, resolution=resolution
        )
    else:
        directory = config.paths.processed / description.key
        dataset = ParquetDataSource(directory, description, resolution).load()

    spec = GridSpec(
        horizon_days=description.horizon_days,
        min_account_age_days=config.business.min_account_age_days,
        min_history_days=config.features.min_history_days,
        observation_frequency=config.features.observation_frequency,
        windows_days=tuple(config.features.windows_days),
        resolution=resolution,
        confirmation_delay_days=description.confirmation_delay_days,
    )
    training = build_training_set(dataset, spec)
    logger.info(
        "training set built",
        extra={
            "rows": len(training.grid),
            "positives": int(training.target.sum()),
            "features": training.features.shape[1],
            "seconds": round(time.monotonic() - started),
        },
    )
    return training


def _selection_settings(config: AppConfig, description: SourceDescription) -> SelectionSettings:
    """Return what the inner selection needs, from the configuration."""
    return SelectionSettings(
        k=config.business.weekly_capacity_k,
        frequency=config.evaluation.scoring_period,
        horizon_days=description.horizon_days,
        embargo_days=description.embargo_days,
        seed=config.project.random_seed,
        confirmation_delay_days=description.confirmation_delay_days,
    )


def _compare(config: AppConfig, description: SourceDescription, training: TrainingSet) -> None:
    """Run every ranking through the folds, write the report and print it."""
    folds = temporal_folds(
        training.grid["T0"],
        n_splits=config.evaluation.n_splits,
        horizon_days=description.horizon_days,
        embargo_days=description.embargo_days,
        confirmation_delay_days=description.confirmation_delay_days,
    )
    selection = _selection_settings(config, description)
    candidates = param_candidates(config.model.param_grid)
    boosted_finance = XGBoostScorer(candidates, selection, FINANCE_ONLY, "xgboost_finance")
    boosted = XGBoostScorer(candidates, selection)
    strengths = config.evaluation.logistic_regularisation
    tuned_finance = TunedLogisticScorer(
        strengths, selection, FINANCE_ONLY, "logistic_tuned_finance"
    )
    tuned = TunedLogisticScorer(strengths, selection)
    scorers: list[Scorer] = [
        RandomScorer(config.project.random_seed),
        RevenueScorer(),
        LogisticScorer(families=FINANCE_ONLY, name="logistic_finance"),
        LogisticScorer(),
        tuned_finance,
        tuned,
        boosted_finance,
        boosted,
    ]
    result = evaluate_scorers(
        training, folds, scorers, selection.k, config.evaluation.scoring_period
    )
    written = write_evaluation_report(
        result,
        config.paths.reports / description.key / "models",
        description.label,
        description.is_synthetic,
        config.evaluation.scoring_period,
    )

    print(f"source      : {description.label} (synthetique : {description.is_synthetic})")
    print(f"grille      : {len(training.grid):,} couples, {int(training.target.sum()):,} positifs")
    print(f"variables   : {training.features.shape[1]}")
    print(f"plis        : {len(folds)}")
    print(summarise(result).round(4).to_string(index=False))
    for tuned_scorer in (tuned_finance, tuned):
        for position, strength in enumerate(tuned_scorer.selections):
            print(
                f"{tuned_scorer.name:<22} pli {position} : C={strength.params} "
                f"{strength.fallback_reason}"
            )
    for boosted_scorer in (boosted_finance, boosted):
        for position, chosen in enumerate(boosted_scorer.selections):
            params = asdict(chosen.params)
            print(f"{boosted_scorer.name:<22} pli {position} : {params} {chosen.fallback_reason}")
    for path in written:
        print(f"ecrit       : {path}")


def _train_and_explain(
    config: AppConfig, description: SourceDescription, training: TrainingSet
) -> None:
    """Train the final model, save and reload it, and explain the last period."""
    mapping = load_feature_mapping(config.paths.feature_mapping)
    model = train_model(
        training,
        TrainingSettings(
            candidates=param_candidates(config.model.param_grid),
            selection=_selection_settings(config, description),
            significance_quantile=config.model.significance_quantile,
        ),
        ModelIdentity(config.project.version, description.label, description.is_synthetic),
        mapping,
    )
    reloaded = load_model(save_model(model, config.paths.models / description.key))
    threshold = reloaded.metadata.significance_threshold
    print(f"modele      : {reloaded.metadata.model_version} {reloaded.metadata.params}")
    print(f"seuil       : {threshold:.4f}")

    # The last observation date, explained as the Monday list would be.
    k = config.business.weekly_capacity_k
    last = training.grid["T0"].max()
    rows = training.grid.index[training.grid["T0"] == last]
    features = training.features.loc[rows]
    aggregated = aggregate_by_origin(reloaded.contributions(features))
    factors = factor_labels(
        top_factors(aggregated, threshold, config.business.top_factors), mapping
    )
    listing = (
        training.grid.loc[rows, ["T0", "client_id", "mrr", "y"]]
        .assign(score=reloaded.score(features))
        .join(factors)
        .sort_values(["score", "mrr", "client_id"], ascending=[False, False, True], kind="stable")
        .head(k)
    )
    listing_path = config.paths.reports / description.key / "models" / "factors_last_period.csv"
    with listing_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# {source_banner(description.label, description.is_synthetic)}\n")
        listing.to_csv(handle, index=False)

    without_factor = (listing[f"{FACTOR_COLUMN_PREFIX}1"] == "").mean()
    print(f"periode     : {last:%Y-%m-%d}, {len(rows):,} comptes")
    # In sample: the final model was trained on these very rows. The count only
    # shows the listing is coherent, it measures nothing. The measure is above.
    print(f"top {k:<7} : {int(listing['y'].sum())} partis, en echantillon, pas une mesure")
    print(f"sans motif  : {without_factor:.0%} de la liste")
    print("contribution positive moyenne par variable d'origine, derniere periode :")
    print(aggregated.clip(lower=0.0).mean().sort_values(ascending=False).head(10).round(4))
    print(f"ecrit       : {listing_path}")


def main(argv: list[str] | None = None) -> int:
    """Run the comparison, train the final model and explain the last period."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["kkbox", "synthetic"], default=None)
    parser.add_argument("--accounts", type=int, default=None, help="synthetic accounts")
    arguments = parser.parse_args(argv)

    config = load_config()
    key = arguments.source or config.active_source
    description = SourceDescription.from_profile(key, config.sources.as_mapping()[key])
    training = _load_training(config, description, arguments.accounts)
    _compare(config, description, training)
    _train_and_explain(config, description, training)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
