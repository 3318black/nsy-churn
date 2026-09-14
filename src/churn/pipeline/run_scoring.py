"""Score one date and write the export, from the command line.

    uv run python -m churn.pipeline.run_scoring --source kkbox
    uv run python -m churn.pipeline.run_scoring --source kkbox --date 2017-03-27

Reads the contract tables of the source and the most recent model saved for it,
scores every eligible account on the date, and writes
``paths.exports/<source>/scoring_<date>`` in Parquet, CSV and JSON.

No training happens here and no network is used. The model comes from
``scripts/train_model.py``. Without ``--date``, the scoring date is the last
observation date the journal allows.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from churn.config import AppConfig, load_config, load_feature_mapping
from churn.data.schemas import Dataset
from churn.data.sources import ParquetDataSource, SourceDescription
from churn.data.synthetic import generate_dataset
from churn.features.build import GridSpec, build_scoring_set
from churn.models.registry import METADATA_FILE, ModelMetadata, TrainedModel, load_model
from churn.pipeline.schemas import FACTOR_COLUMNS
from churn.pipeline.scoring import ExportSettings, score_accounts
from churn.pipeline.sinks import default_sinks, write_batch

__all__ = ["check_model_source", "latest_model_folder", "main"]

logger = logging.getLogger("run_scoring")


def latest_model_folder(directory: Path) -> Path:
    """Return the most recently trained model saved under ``directory``.

    Args:
        directory: the models directory of one source.

    Returns:
        The folder of the model with the latest training time.

    Raises:
        FileNotFoundError: when no model is saved there.
    """
    folders = (
        [folder for folder in directory.iterdir() if (folder / METADATA_FILE).is_file()]
        if directory.is_dir()
        else []
    )
    if not folders:
        message = f"no saved model under {directory}: run scripts/train_model.py first"
        raise FileNotFoundError(message)

    def trained_at(folder: Path) -> tuple[str, str]:
        text = (folder / METADATA_FILE).read_text(encoding="utf-8")
        return ModelMetadata.from_json(text).created_at, folder.name

    return max(folders, key=trained_at)


def check_model_source(model: TrainedModel, description: SourceDescription) -> None:
    """Refuse a model trained on another source than the one being scored.

    A model trained on simulated data scoring real accounts would produce a list
    that looks legitimate and means nothing, decision D2.

    Raises:
        ValueError: when the sources differ.
    """
    metadata = model.metadata
    if metadata.is_synthetic != description.is_synthetic or (
        metadata.source_label != description.label
    ):
        message = (
            f"model {metadata.model_version} was trained on '{metadata.source_label}', "
            f"it cannot score '{description.label}'"
        )
        raise ValueError(message)


def _load_dataset(
    config: AppConfig, description: SourceDescription, accounts: int | None
) -> Dataset:
    """Load the contract tables of the source."""
    resolution = config.features.datetime_resolution
    if description.key == "synthetic":
        profile = config.sources.synthetic
        if accounts:
            profile = profile.model_copy(update={"n_accounts": accounts})
        return generate_dataset(profile, seed=config.project.random_seed, resolution=resolution)
    directory = config.paths.processed / description.key
    return ParquetDataSource(directory, description, resolution).load()


def main(argv: list[str] | None = None) -> int:
    """Score one date and write the three export files."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["kkbox", "synthetic"], default=None)
    parser.add_argument("--date", default=None, help="scoring date, AAAA-MM-JJ, in UTC")
    parser.add_argument("--model", type=Path, default=None, help="folder of a saved model")
    parser.add_argument("--accounts", type=int, default=None, help="synthetic accounts")
    arguments = parser.parse_args(argv)

    config = load_config()
    key = arguments.source or config.active_source
    description = SourceDescription.from_profile(key, config.sources.as_mapping()[key])
    dataset = _load_dataset(config, description, arguments.accounts)

    model = load_model(arguments.model or latest_model_folder(config.paths.models / key))
    check_model_source(model, description)

    spec = GridSpec(
        horizon_days=description.horizon_days,
        min_account_age_days=config.business.min_account_age_days,
        min_history_days=config.features.min_history_days,
        observation_frequency=config.features.observation_frequency,
        windows_days=tuple(config.features.windows_days),
        resolution=config.features.datetime_resolution,
        confirmation_delay_days=description.confirmation_delay_days,
    )
    scoring_date = pd.Timestamp(arguments.date, tz="UTC") if arguments.date else None
    scoring = build_scoring_set(dataset, spec, scoring_date)

    settings = ExportSettings(
        k=config.business.weekly_capacity_k,
        top_factors=config.business.top_factors,
        max_label_length=config.export.max_label_length,
        source_label=description.label,
        is_synthetic=description.is_synthetic,
    )
    batch = score_accounts(
        scoring, model, load_feature_mapping(config.paths.feature_mapping), settings
    )
    written = write_batch(batch, config.paths.exports / key, default_sinks(config.export))

    rows = batch.rows
    head = rows.loc[rows["is_top_k"].astype(bool)]
    without_factor = float((head[FACTOR_COLUMNS[0]] == "").mean()) if len(head) else 0.0
    print(f"source      : {description.label} (synthetique : {description.is_synthetic})")
    print(f"date        : {batch.date_scoring.isoformat()}")
    print(f"modele      : {batch.model_version}")
    print(f"lot         : {batch.batch_run_id}")
    print(f"comptes     : {len(rows):,} scores, {len(head)} en tete de liste")
    print(f"sans motif  : {without_factor:.0%} de la tete de liste")
    for path in written:
        print(f"ecrit       : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
