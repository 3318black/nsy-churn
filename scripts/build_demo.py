"""Build the demonstration root published with the online interface, decision D22.

    uv run python scripts/build_demo.py

The online interface publishes no individual KKBox data: the competition rules
govern redistribution, and publishing identifiers or listening histories was not
retained. It publishes instead:

- the aggregated evaluation measures of KKBox, which describe no subscriber;
- a complete simulated chain, journal, export, contributions and report, so the
  list and the account sheet can be browsed under the simulated data banner.

Everything lands under ``demo/``, a project root the interface reads through the
``NSY_CHURN_ROOT`` variable. The directory is rebuilt from scratch at every run,
with the configured seed, so the same code yields the same files.

Prerequisite: the KKBox evaluation report, from ``scripts/train_model.py``.
"""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn.config import PROJECT_ROOT, AppConfig, load_config, load_feature_mapping
from churn.data.sources import write_dataset
from churn.data.synthetic import generate_dataset
from churn.evaluation.baselines import Scorer, default_baselines
from churn.evaluation.protocol import evaluate_scorers
from churn.evaluation.report import write_evaluation_report
from churn.evaluation.splitting import temporal_folds
from churn.features.build import GridSpec, build_scoring_set, build_training_set
from churn.interface.readers import PERIODS_FILE, SUMMARY_FILE
from churn.models.train import (
    ModelIdentity,
    SelectionSettings,
    TrainingSettings,
    XGBoostScorer,
    param_candidates,
    train_model,
)
from churn.pipeline.scoring import ExportSettings, score_accounts
from churn.pipeline.sinks import ContributionsSink, CsvSink, ParquetSink, Sink, write_batch

logger = logging.getLogger("build_demo")

#: Directory of the demonstration root, inside the repository.
DEMO_ROOT = PROJECT_ROOT / "demo"

#: Simulated accounts of the demonstration. Small on purpose: the files are
#: versioned, and the simulated chain only has to be browsable.
DEMO_ACCOUNTS = 300

#: The only KKBox files published: averaged measures, one row per ranking or per
#: ranking and week. Never an export, a journal or a listing of accounts.
PUBLISHED_KKBOX_REPORTS = (SUMMARY_FILE, PERIODS_FILE)

#: Columns whose presence would reveal individual data.
INDIVIDUAL_COLUMNS = frozenset({"client_id", "msno"})

#: Shown online in place of the KKBox list and account sheet.
MISSING_EXPORT_NOTICE = (
    "La liste des abonnés KKBox n'est pas publiée en ligne : ces données individuelles "
    "relèvent des règles de la compétition, et seules les mesures agrégées de performance "
    "sont montrées. Pour parcourir la liste et la fiche d'un compte, choisissez la source "
    "« Jeu synthetique genere localement » : une chaîne complète y tourne sur des données "
    "simulées."
)


def _write_config(root: Path) -> AppConfig:
    """Copy the configuration into the demonstration root, with the online notice."""
    shutil.copytree(PROJECT_ROOT / "config", root / "config")
    path = root / "config" / "config.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["active_source"] = "kkbox"
    payload["interface"]["missing_export_notice"] = MISSING_EXPORT_NOTICE
    header = (
        "# Configuration de la demonstration en ligne, generee par scripts/build_demo.py.\n"
        "# Ne pas modifier a la main : relancer le script. Voir decision D22.\n"
    )
    body = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    path.write_text(header + body, encoding="utf-8")
    return load_config(project_root=root)


def _publish_kkbox_aggregates(config: AppConfig, demo: AppConfig) -> list[Path]:
    """Copy the aggregated KKBox measures, refusing any file with individual data."""
    source = config.paths.reports / "kkbox" / "models"
    target = demo.paths.reports / "kkbox" / "models"
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in PUBLISHED_KKBOX_REPORTS:
        path = source / name
        if not path.is_file():
            message = f"missing {path}: run scripts/train_model.py --source kkbox first"
            raise FileNotFoundError(message)
        columns = set(pd.read_csv(path, comment="#", nrows=0).columns)
        if columns & INDIVIDUAL_COLUMNS:
            message = f"{name} carries individual columns {columns & INDIVIDUAL_COLUMNS}"
            raise ValueError(message)
        written.append(Path(shutil.copy2(path, target / name)))
    return written


def _build_simulated_chain(demo: AppConfig) -> list[Path]:
    """Run the whole simulated chain into the demonstration root."""
    profile = demo.sources.synthetic.model_copy(update={"n_accounts": DEMO_ACCOUNTS})
    seed = demo.project.random_seed
    dataset = generate_dataset(profile, seed=seed, resolution=demo.features.datetime_resolution)
    written = list(write_dataset(dataset, demo.paths.processed / "synthetic").values())

    spec = GridSpec(
        horizon_days=profile.horizon_days,
        min_account_age_days=demo.business.min_account_age_days,
        min_history_days=demo.features.min_history_days,
        observation_frequency=demo.features.observation_frequency,
        windows_days=tuple(demo.features.windows_days),
        resolution=demo.features.datetime_resolution,
        confirmation_delay_days=profile.confirmation_delay_days,
    )
    training = build_training_set(dataset, spec)
    selection = SelectionSettings(
        k=demo.business.weekly_capacity_k,
        frequency=demo.evaluation.scoring_period,
        horizon_days=profile.horizon_days,
        embargo_days=profile.embargo_days,
        seed=seed,
        confirmation_delay_days=profile.confirmation_delay_days,
    )
    candidates = param_candidates(demo.model.param_grid)

    folds = temporal_folds(
        training.grid["T0"],
        demo.evaluation.n_splits,
        profile.horizon_days,
        profile.embargo_days,
        profile.confirmation_delay_days,
    )
    scorers: list[Scorer] = [*default_baselines(seed), XGBoostScorer(candidates, selection)]
    result = evaluate_scorers(training, folds, scorers, selection.k, selection.frequency)
    # Only the data files the interface reads are kept. The Markdown summary
    # carries its production time and would change at every rebuild.
    reports = demo.paths.reports / "synthetic" / "models"
    reports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        report = write_evaluation_report(
            result, Path(scratch), profile.label, True, selection.frequency
        )
        for path in report:
            if path.name in PUBLISHED_KKBOX_REPORTS:
                written.append(Path(shutil.copy2(path, reports / path.name)))

    mapping = load_feature_mapping(demo.paths.feature_mapping)
    model = train_model(
        training,
        TrainingSettings(candidates, selection, demo.model.significance_quantile),
        ModelIdentity(demo.project.version, profile.label, True),
        mapping,
    )
    settings = ExportSettings(
        k=demo.business.weekly_capacity_k,
        top_factors=demo.business.top_factors,
        max_label_length=demo.export.max_label_length,
        source_label=profile.label,
        is_synthetic=True,
    )
    batch = score_accounts(build_scoring_set(dataset, spec), model, mapping, settings)
    # The files the interface reads: rows, contributions, and the CSV it offers
    # to download. The JSON, meant for a dedicated front end, is not published.
    export = demo.export
    sinks: list[Sink] = [
        ParquetSink(),
        CsvSink(export.csv_encoding, export.csv_separator, export.csv_decimal),
        ContributionsSink(),
    ]
    written += write_batch(batch, demo.paths.exports / "synthetic", sinks)
    return written


def main() -> int:
    """Rebuild ``demo/`` from scratch."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    config = load_config()
    if DEMO_ROOT.exists():
        shutil.rmtree(DEMO_ROOT)
    demo = _write_config(DEMO_ROOT)
    written = [
        DEMO_ROOT / "config" / "config.yaml",
        *_publish_kkbox_aggregates(config, demo),
        *_build_simulated_chain(demo),
    ]
    total = 0
    for path in written:
        size = path.stat().st_size
        total += size
        print(f"{size / 1024:>9.1f} Ko  {path.relative_to(PROJECT_ROOT)}")
    print(f"{total / 1024 / 1024:>9.2f} Mo  au total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
