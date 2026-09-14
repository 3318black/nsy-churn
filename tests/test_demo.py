"""Tests of the demonstration root published with the online interface, decision D22."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest
from streamlit.testing.v1 import AppTest

from churn.config import PROJECT_ROOT, load_config

DEMO = PROJECT_ROOT / "demo"

APP = PROJECT_ROOT / "app" / "streamlit_app.py"

#: The only KKBox files the demonstration may hold: averaged measures.
PUBLISHED_KKBOX_FILES = [
    "reports/kkbox/models/evaluation_precision_per_period.csv",
    "reports/kkbox/models/evaluation_summary.csv",
]

#: Identifiers of the synthetic generator. A KKBox identifier looks nothing like it.
SYNTHETIC_ID = re.compile(r"^C\d{6}$")


def _files() -> list[Path]:
    """Return every file of the demonstration root."""
    assert DEMO.is_dir(), "demo/ is missing: run scripts/build_demo.py"
    return sorted(path for path in DEMO.rglob("*") if path.is_file())


def test_the_demo_publishes_only_aggregated_kkbox_measures() -> None:
    """Guard of decision D22: no KKBox export, journal or listing goes online."""
    kkbox = [
        path.relative_to(DEMO).as_posix()
        for path in _files()
        if "kkbox" in path.relative_to(DEMO).parts
    ]
    assert kkbox == PUBLISHED_KKBOX_FILES
    for name in kkbox:
        columns = set(pd.read_csv(DEMO / name, comment="#", nrows=0).columns)
        assert not columns & {"client_id", "msno"}, f"{name} carries an individual column"


def test_every_account_of_the_demo_is_simulated() -> None:
    """Any identifier published must come from the synthetic generator."""
    checked = 0
    for path in _files():
        if path.suffix != ".parquet":
            continue
        if "client_id" not in pq.read_schema(path).names:
            continue
        identifiers = pd.read_parquet(path, columns=["client_id"])["client_id"]
        assert identifiers.map(lambda value: bool(SYNTHETIC_ID.match(value))).all(), path
        checked += 1
    assert checked >= 3, "the journal, the export and the contributions should be checked"


def test_the_demo_configuration_explains_the_missing_list() -> None:
    """Online, a missing KKBox list is explained, not presented as a command to run."""
    config = load_config(project_root=DEMO)
    assert config.active_source == "kkbox"
    assert config.interface.missing_export_notice.strip()


def test_the_local_configuration_keeps_the_command_hint(config_path: Path) -> None:
    """Locally, the notice stays empty and the interface names the command instead."""
    assert load_config(config_path).interface.missing_export_notice == ""


def _run(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """Run the interface on the demonstration root."""
    monkeypatch.setenv("NSY_CHURN_ROOT", str(DEMO))
    app = AppTest.from_file(str(APP), default_timeout=120)
    app.run()
    return app


def test_the_online_interface_shows_the_kkbox_performance(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real argument goes online: the six rankings measured on KKBox."""
    app = _run(monkeypatch)
    assert not app.exception
    alerts = [element.value for element in app.info]
    assert any(text.startswith("Source :") for text in alerts)
    assert any("n'est pas publiée" in text for text in alerts)

    app.sidebar.radio[0].set_value("Performance du modèle").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 6


def test_the_online_interface_browses_the_simulated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """The list and the account sheet run on simulated data, under their banner."""
    app = _run(monkeypatch)
    app.sidebar.selectbox[0].set_value("synthetic").run()
    assert not app.exception
    assert any("Données simulées" in element.value for element in app.warning)
    assert len(app.dataframe[0].value) == load_config(project_root=DEMO).business.weekly_capacity_k

    app.sidebar.radio[0].set_value("Fiche d'un compte").run()
    assert not app.exception
    assert len(app.metric) == 4
