"""Tests of the Streamlit interface, run headless with Streamlit's AppTest."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest
import yaml
from streamlit.testing.v1 import AppTest

from churn.config import PROJECT_ROOT, AppConfig, load_config, load_feature_mapping
from churn.data.sources import write_dataset
from churn.data.synthetic import generate_dataset
from churn.evaluation.baselines import default_baselines
from churn.evaluation.protocol import evaluate_scorers
from churn.evaluation.report import write_evaluation_report
from churn.evaluation.splitting import temporal_folds
from churn.features.build import GridSpec, build_scoring_set, build_training_set
from churn.models.train import (
    BoosterParams,
    ModelIdentity,
    SelectionSettings,
    TrainingSettings,
    train_model,
)
from churn.pipeline.scoring import ExportSettings, score_accounts
from churn.pipeline.sinks import default_sinks, write_batch

APP = PROJECT_ROOT / "app" / "streamlit_app.py"

HOME, LIST, ACCOUNT, PERFORMANCE = SCREENS = (
    "Le projet",
    "Liste du lundi",
    "Fiche d'un compte",
    "Performance du modèle",
)

SMALL = (BoosterParams(max_depth=2, n_estimators=20, learning_rate=0.3),)


def _copy_config(root: Path) -> None:
    """Give a temporary project root the configuration of the repository."""
    shutil.copytree(PROJECT_ROOT / "config", root / "config")


@pytest.fixture
def empty_root(tmp_path: Path) -> Path:
    """A project root holding the configuration and nothing else."""
    _copy_config(tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def populated_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project root holding a synthetic journal, export and evaluation report."""
    root = tmp_path_factory.mktemp("interface")
    _copy_config(root)
    config = load_config(project_root=root)
    profile = config.sources.synthetic.model_copy(update={"n_accounts": 300})
    dataset = generate_dataset(profile, seed=config.project.random_seed, resolution="us")
    write_dataset(dataset, config.paths.processed / "synthetic")

    spec = GridSpec(
        horizon_days=profile.horizon_days,
        min_account_age_days=config.business.min_account_age_days,
        min_history_days=config.features.min_history_days,
        observation_frequency=config.features.observation_frequency,
        windows_days=tuple(config.features.windows_days),
        resolution="us",
    )
    training = build_training_set(dataset, spec)
    mapping = load_feature_mapping(config.paths.feature_mapping)
    selection = SelectionSettings(
        k=config.business.weekly_capacity_k,
        frequency=config.evaluation.scoring_period,
        horizon_days=profile.horizon_days,
        embargo_days=profile.embargo_days,
        seed=config.project.random_seed,
    )
    model = train_model(
        training,
        TrainingSettings(SMALL, selection, 0.75),
        ModelIdentity("0.0.0", profile.label, True),
        mapping,
    )
    settings = ExportSettings(
        k=config.business.weekly_capacity_k,
        top_factors=config.business.top_factors,
        max_label_length=config.export.max_label_length,
        source_label=profile.label,
        is_synthetic=True,
    )
    batch = score_accounts(build_scoring_set(dataset, spec), model, mapping, settings)
    write_batch(batch, config.paths.exports / "synthetic", default_sinks(config.export))

    folds = temporal_folds(training.grid["T0"], 2, profile.horizon_days, profile.embargo_days)
    result = evaluate_scorers(
        training, folds, default_baselines(seed=1), k=selection.k, frequency=selection.frequency
    )
    write_evaluation_report(
        result, config.paths.reports / "synthetic" / "models", profile.label, True, "W-MON"
    )
    return root


def _run(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str | None = None,
    screen: str | None = None,
) -> AppTest:
    """Run the application on a project root, then select a source and a screen."""
    monkeypatch.setenv("NSY_CHURN_ROOT", str(root))
    app = AppTest.from_file(str(APP), default_timeout=120)
    app.run()
    if source is not None:
        app.sidebar.selectbox[0].set_value(source).run()
    if screen is not None:
        app.sidebar.radio[0].set_value(screen).run()
    return app


def _alerts(app: AppTest) -> list[str]:
    """Return the text of every information and warning box."""
    return [element.value for element in [*app.info, *app.warning]]


@pytest.mark.parametrize("screen", SCREENS)
def test_the_app_starts_on_an_empty_export(
    empty_root: Path, monkeypatch: pytest.MonkeyPatch, screen: str
) -> None:
    """Criterion 3 of lot 7: no export yet is a message, never a crash."""
    app = _run(empty_root, monkeypatch, screen=screen)
    assert not app.exception
    alerts = _alerts(app)
    assert any(text.startswith("Source :") for text in alerts), "the source banner is missing"
    assert any("Aucun" in text for text in alerts), "the missing file is not explained"


@pytest.mark.parametrize("screen", SCREENS)
def test_the_simulated_banner_is_on_every_screen(
    populated_root: Path, monkeypatch: pytest.MonkeyPatch, screen: str
) -> None:
    """Criterion 4 of lot 7, decision D2: the source is stated wherever a figure shows."""
    app = _run(populated_root, monkeypatch, source="synthetic", screen=screen)
    assert not app.exception
    assert any("Données simulées" in element.value for element in app.warning)


def test_the_home_screen_opens_the_application(
    populated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first visit lands on the project, with its key figures read from the report."""
    app = _run(populated_root, monkeypatch, source="synthetic")
    assert not app.exception
    assert app.title[0].value == HOME
    labels = {metric.label for metric in app.metric}
    assert {"Tri par revenu", "Régression logistique"} <= labels
    assert all("départs trouvés" in metric.value for metric in app.metric)


def test_the_list_shows_the_calls_of_the_week(
    populated_root: Path, monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    """Screen 1: the head of the list, in rank order, read from the export."""
    app = _run(populated_root, monkeypatch, source="synthetic", screen=LIST)
    assert not app.exception
    table = app.dataframe[0].value
    assert len(table) == config.business.weekly_capacity_k
    assert table["rang_priorite"].tolist() == list(range(1, len(table) + 1))


def test_the_account_sheet_says_what_to_do_and_who_the_subscriber_is(
    populated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Screen 2: motives with their action, a profile, contributions and history."""
    app = _run(populated_root, monkeypatch, source="synthetic", screen=ACCOUNT)
    assert not app.exception
    labels = {metric.label for metric in app.metric}
    assert {"Rang", "Décile de risque", "Inscription", "Dernière facture"} <= labels
    assert any(caption.value.startswith("Action conseillée") for caption in app.caption)
    alerts = _alerts(app)
    assert not any("contributions" in text for text in alerts)
    assert not any("historique" in text for text in alerts)
    assert not any("profil" in text for text in alerts)


def test_the_performance_screen_reads_the_report(
    populated_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Screen 3: the measures come from the evaluation report files."""
    app = _run(populated_root, monkeypatch, source="synthetic", screen=PERFORMANCE)
    assert not app.exception
    assert app.dataframe
    assert not any("rapport" in text for text in _alerts(app))


def test_the_capacity_comes_from_the_configuration(
    empty_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 2 of lot 7: no business value is written in the application."""
    path = empty_root / "config" / "config.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["business"]["weekly_capacity_k"] = 7
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    app = _run(empty_root, monkeypatch)
    assert not app.exception
    assert any("Capacité de 7 appels" in text for text in _alerts(app))


def test_the_app_never_trains_nor_scores() -> None:
    """Criterion 1 of lot 7: the application imports no training or scoring code.

    Imports are read from the syntax tree, so a module merely named in a message,
    such as the command to run, does not count.
    """
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    source = " ".join(
        (node.module or "")
        if isinstance(node, ast.ImportFrom)
        else " ".join(alias.name for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
    )
    assert "churn.interface.readers" in source, "the import walk found nothing"
    for forbidden in (
        "churn.models",
        "churn.features",
        "churn.evaluation",
        "churn.pipeline.scoring",
        "churn.pipeline.run_scoring",
        "xgboost",
        "sklearn",
    ):
        assert forbidden not in source, f"the interface imports {forbidden}"
