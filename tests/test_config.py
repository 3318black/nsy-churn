"""Configuration loading: nominal path, missing keys and cross validation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from churn.config import (
    AppConfig,
    ConfigError,
    FeatureSource,
    KkboxSourceConfig,
    SyntheticSourceConfig,
    load_config,
    load_feature_mapping,
)

WriteYaml = Callable[[dict[str, Any]], Path]


def test_real_config_loads(config: AppConfig, raw_config: dict[str, Any]) -> None:
    """The configuration file of the repository is valid."""
    assert config.project.name == raw_config["project"]["name"]
    assert config.active_source == raw_config["active_source"]
    assert config.business.top_factors == raw_config["business"]["top_factors"]
    assert config.features.windows_days == raw_config["features"]["windows_days"]
    assert config.model.param_grid.max_depth == raw_config["model"]["param_grid"]["max_depth"]


def test_source_profiles_are_typed_by_role(config: AppConfig) -> None:
    """Each profile is loaded with the fields of its own role, see decision D14."""
    profiles = config.sources.as_mapping()
    assert set(profiles) == {"kkbox", "synthetic"}
    assert isinstance(config.sources.kkbox, KkboxSourceConfig)
    assert isinstance(config.sources.synthetic, SyntheticSourceConfig)
    assert config.sources.kkbox.is_synthetic is False
    assert config.sources.synthetic.is_synthetic is True
    assert config.sources.kkbox.raw_files.transactions.endswith(".csv")


def test_active_profile_returns_the_declared_profile(config: AppConfig) -> None:
    """The accessor resolves ``active_source`` against the declared profiles."""
    assert config.active_profile() is config.sources.kkbox


def test_paths_are_absolute_and_rooted_in_the_project(
    config: AppConfig,
    project_root: Path,
) -> None:
    """Every path of the ``paths`` section is exposed as an absolute Path."""
    paths = [
        config.paths.raw,
        config.paths.processed,
        config.paths.exports,
        config.paths.models,
        config.paths.reports,
        config.paths.feature_mapping,
    ]
    for path in paths:
        assert isinstance(path, Path)
        assert path.is_absolute()
        assert path.is_relative_to(project_root)


def test_paths_follow_the_given_project_root(config_path: Path, tmp_path: Path) -> None:
    """No module builds a path on its own: the root is injected at load time."""
    loaded = load_config(config_path, project_root=tmp_path)
    assert loaded.paths.raw == tmp_path / "data" / "raw"


def test_missing_file_is_reported(tmp_path: Path) -> None:
    """A missing configuration file fails while naming the expected path."""
    missing = tmp_path / "absent.yaml"
    with pytest.raises(ConfigError, match="not found"):
        load_config(missing)


@pytest.mark.parametrize(
    ("path_to_remove", "expected_location"),
    [
        (("business",), "business"),
        (("project", "random_seed"), "project.random_seed"),
        (("sources", "kkbox", "horizon_days"), "sources.kkbox.horizon_days"),
        (("sources", "synthetic", "annual_churn_rate"), "sources.synthetic.annual_churn_rate"),
        (("paths", "exports"), "paths.exports"),
    ],
)
def test_missing_key_fails_and_names_the_key(
    raw_config: dict[str, Any],
    write_yaml: WriteYaml,
    path_to_remove: tuple[str, ...],
    expected_location: str,
) -> None:
    """No silent default: a missing key stops the load and is named."""
    node: Any = raw_config
    for key in path_to_remove[:-1]:
        node = node[key]
    del node[path_to_remove[-1]]

    with pytest.raises(ConfigError) as error:
        load_config(write_yaml(raw_config))

    message = str(error.value)
    assert expected_location in message
    assert "Field required" in message


def test_unknown_key_is_rejected(raw_config: dict[str, Any], write_yaml: WriteYaml) -> None:
    """A typo never passes silently."""
    raw_config["business"]["weekly_capcity_k"] = 50

    with pytest.raises(ConfigError, match="weekly_capcity_k"):
        load_config(write_yaml(raw_config))


@pytest.mark.parametrize("profile_name", ["kkbox", "synthetic"])
def test_embargo_shorter_than_horizon_fails_and_names_the_profile(
    raw_config: dict[str, Any],
    write_yaml: WriteYaml,
    profile_name: str,
) -> None:
    """Decision D4: a short embargo lets the target resolve inside the test period."""
    profile = raw_config["sources"][profile_name]
    profile["embargo_days"] = profile["horizon_days"] - 1

    with pytest.raises(ConfigError) as error:
        load_config(write_yaml(raw_config))

    message = str(error.value)
    assert f"profile '{profile_name}'" in message
    assert "embargo_days" in message
    assert "horizon_days" in message


def test_embargo_equal_to_horizon_is_accepted(
    raw_config: dict[str, Any],
    write_yaml: WriteYaml,
) -> None:
    """The rule is an inequality, not a strict one."""
    for profile in raw_config["sources"].values():
        profile["embargo_days"] = profile["horizon_days"]

    loaded = load_config(write_yaml(raw_config))

    assert loaded.sources.kkbox.embargo_days == loaded.sources.kkbox.horizon_days


def test_unknown_active_source_fails(raw_config: dict[str, Any], write_yaml: WriteYaml) -> None:
    """An active source that matches no profile stops the load."""
    raw_config["active_source"] = "postgres"

    with pytest.raises(ConfigError) as error:
        load_config(write_yaml(raw_config))

    message = str(error.value)
    assert "postgres" in message
    assert "kkbox" in message
    assert "synthetic" in message


def test_mislabelled_synthetic_flag_is_rejected(
    raw_config: dict[str, Any],
    write_yaml: WriteYaml,
) -> None:
    """Decision D2 rests on this flag, so it may not contradict the profile."""
    raw_config["sources"]["kkbox"]["is_synthetic"] = True

    with pytest.raises(ConfigError, match=r"sources\.kkbox\.is_synthetic"):
        load_config(write_yaml(raw_config))


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    """An empty file is not an empty configuration."""
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ConfigError, match="must be a mapping"):
        load_config(path)


def test_real_feature_mapping_loads(config: AppConfig) -> None:
    """The feature mapping of the repository is valid and typed."""
    mapping = load_feature_mapping(config.paths.feature_mapping)

    assert mapping
    assert all(isinstance(entry.source, FeatureSource) for entry in mapping.values())
    assert mapping["nb_connexions_30j"].source is FeatureSource.PRODUCT
    assert mapping["anciennete_jours"].action == ""


def test_feature_source_outside_the_nomenclature_fails(write_yaml: WriteYaml) -> None:
    """The families are a closed nomenclature, see decision D7."""
    payload = {
        "nb_tickets_support_30j": {
            "label": "Hausse des tickets support",
            "source": "MARKETING",
            "action": "Verifier les incidents ouverts",
        }
    }

    with pytest.raises(ConfigError) as error:
        load_feature_mapping(write_yaml(payload))

    message = str(error.value)
    assert "nb_tickets_support_30j.source" in message
    assert "MARKETING" in message or "SUPPORT" in message


def test_feature_action_may_be_empty_but_never_absent(write_yaml: WriteYaml) -> None:
    """An empty action means no possible lever, an absent one means a broken file."""
    complete = {"label": "Anciennete du compte", "source": "GENERAL", "action": ""}
    assert load_feature_mapping(write_yaml({"anciennete_jours": complete}))

    incomplete = {"label": "Anciennete du compte", "source": "GENERAL"}
    with pytest.raises(ConfigError, match=r"anciennete_jours\.action"):
        load_feature_mapping(write_yaml({"anciennete_jours": incomplete}))
