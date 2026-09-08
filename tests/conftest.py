"""Shared fixtures.

The files under ``config/`` are read only. Every faulty configuration is built
as a copy written under ``tmp_path``.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from churn.config import PROJECT_ROOT, AppConfig, load_config
from churn.logging import reset_logging

WriteYaml = Callable[[dict[str, Any]], Path]


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Root of the repository, as the package resolves it."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def config_path(project_root: Path) -> Path:
    """Path of the real configuration file of the repository."""
    return project_root / "config" / "config.yaml"


@pytest.fixture(scope="session")
def config(config_path: Path) -> AppConfig:
    """Configuration of the repository, loaded once."""
    return load_config(config_path)


@pytest.fixture
def raw_config(config_path: Path) -> dict[str, Any]:
    """Mutable copy of the real configuration, as a plain dictionary."""
    with config_path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return copy.deepcopy(payload)


@pytest.fixture
def write_yaml(tmp_path: Path) -> WriteYaml:
    """Return a helper writing a dictionary to a temporary YAML file."""
    counter = 0

    def _write(payload: dict[str, Any]) -> Path:
        nonlocal counter
        counter += 1
        path = tmp_path / f"payload_{counter}.yaml"
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
        return path

    return _write


@pytest.fixture(autouse=True)
def _isolated_logging() -> Iterator[None]:
    """Guarantee that no test inherits the handler installed by another one."""
    reset_logging()
    yield
    reset_logging()
