"""Measure the three baselines through the evaluation protocol.

Criterion 3 of lot 4 requires the baselines to be measured and recorded before
any tree ensemble is trained. This script does exactly that, on the source named
on the command line, and writes the report under ``paths.reports``.

    uv run python scripts/evaluate_baselines.py --source kkbox
    uv run python scripts/evaluate_baselines.py --source synthetic --accounts 2000

No network access. The KKBox source reads the Parquet tables written by
``scripts/download_kkbox.py``; the synthetic source is generated locally.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn.config import load_config
from churn.data.sources import ParquetDataSource, SourceDescription
from churn.data.synthetic import generate_dataset
from churn.evaluation.baselines import default_baselines
from churn.evaluation.protocol import evaluate_scorers, summarise
from churn.evaluation.report import write_evaluation_report
from churn.evaluation.splitting import temporal_folds
from churn.features.build import GridSpec, build_training_set

logger = logging.getLogger("evaluate_baselines")


def main(argv: list[str] | None = None) -> int:
    """Build the training set, run the baselines and write the report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["kkbox", "synthetic"], default=None)
    parser.add_argument("--accounts", type=int, default=None, help="synthetic accounts")
    arguments = parser.parse_args(argv)

    config = load_config()
    key = arguments.source or config.active_source
    profile = config.sources.as_mapping()[key]
    description = SourceDescription.from_profile(key, profile)
    resolution = config.features.datetime_resolution

    started = time.monotonic()
    if key == "synthetic":
        synthetic = config.sources.synthetic
        if arguments.accounts:
            synthetic = synthetic.model_copy(update={"n_accounts": arguments.accounts})
        dataset = generate_dataset(
            synthetic, seed=config.project.random_seed, resolution=resolution
        )
    else:
        directory = config.paths.processed / key
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

    folds = temporal_folds(
        training.grid["T0"],
        n_splits=config.evaluation.n_splits,
        horizon_days=description.horizon_days,
        embargo_days=description.embargo_days,
        confirmation_delay_days=description.confirmation_delay_days,
    )
    result = evaluate_scorers(
        training,
        folds,
        default_baselines(seed=config.project.random_seed),
        k=config.business.weekly_capacity_k,
        frequency=config.evaluation.scoring_period,
    )
    written = write_evaluation_report(
        result,
        config.paths.reports / key,
        description.label,
        description.is_synthetic,
        config.evaluation.scoring_period,
    )

    print(f"source      : {description.label} (synthetique : {description.is_synthetic})")
    print(f"grille      : {len(training.grid):,} couples, {int(training.target.sum()):,} positifs")
    print(f"plis        : {len(folds)}")
    print(summarise(result).round(4).to_string(index=False))
    for path in written:
        print(f"ecrit       : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
