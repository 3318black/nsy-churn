"""Tests of the scoring set, of the export and of its destinations, lot 6."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from churn.config import (
    AppConfig,
    ConfigError,
    FeatureMappingEntry,
    load_config,
    load_feature_mapping,
)
from churn.data.schemas import Dataset
from churn.data.sources import SourceDescription
from churn.data.synthetic import generate_dataset
from churn.features.build import (
    GridSpec,
    ScoringSet,
    TrainingSet,
    build_scoring_set,
    build_training_set,
    observation_dates,
)
from churn.models.registry import TrainedModel, save_model
from churn.models.train import (
    BoosterParams,
    ModelIdentity,
    SelectionSettings,
    TrainingSettings,
    train_model,
)
from churn.pipeline.run_scoring import check_model_source, latest_model_folder
from churn.pipeline.schemas import EXPORT_COLUMNS, FACTOR_COLUMNS, validate_export
from churn.pipeline.scoring import (
    ExportSettings,
    ScoringBatch,
    actionable_origins,
    batch_run_id,
    risk_deciles,
    score_accounts,
)
from churn.pipeline.sinks import PARQUET_METADATA_KEY, default_sinks, write_batch

#: Two small combinations, so the tests stay fast.
SMALL = (
    BoosterParams(max_depth=2, n_estimators=20, learning_rate=0.3),
    BoosterParams(max_depth=3, n_estimators=40, learning_rate=0.1),
)

#: Label of the source the test model is trained on.
SOURCE = "Jeu synthetique de test"


@pytest.fixture(scope="module")
def spec(config: AppConfig) -> GridSpec:
    """Grid specification of the synthetic profile."""
    return GridSpec(
        horizon_days=config.sources.synthetic.horizon_days,
        min_account_age_days=config.business.min_account_age_days,
        min_history_days=config.features.min_history_days,
        observation_frequency=config.features.observation_frequency,
        windows_days=tuple(config.features.windows_days),
        resolution="us",
    )


@pytest.fixture(scope="module")
def dataset(config: AppConfig) -> Dataset:
    """A small synthetic dataset."""
    profile = config.sources.synthetic.model_copy(update={"n_accounts": 300})
    return generate_dataset(profile, seed=config.project.random_seed, resolution="us")


@pytest.fixture(scope="module")
def training(dataset: Dataset, spec: GridSpec) -> TrainingSet:
    """The training set of the dataset."""
    return build_training_set(dataset, spec)


@pytest.fixture(scope="module")
def mapping(config: AppConfig) -> dict[str, FeatureMappingEntry]:
    """The business mapping of the repository."""
    return load_feature_mapping(config.paths.feature_mapping)


@pytest.fixture(scope="module")
def model(
    training: TrainingSet, config: AppConfig, mapping: dict[str, FeatureMappingEntry]
) -> TrainedModel:
    """A small model trained on the synthetic dataset."""
    profile = config.sources.synthetic
    selection = SelectionSettings(
        k=config.business.weekly_capacity_k,
        frequency=config.evaluation.scoring_period,
        horizon_days=profile.horizon_days,
        embargo_days=profile.embargo_days,
        seed=config.project.random_seed,
    )
    return train_model(
        training,
        TrainingSettings(SMALL, selection, 0.75),
        ModelIdentity("0.0.0", SOURCE, True),
        mapping,
    )


@pytest.fixture(scope="module")
def scoring(dataset: Dataset, spec: GridSpec) -> ScoringSet:
    """The accounts to score on the default date."""
    return build_scoring_set(dataset, spec)


@pytest.fixture(scope="module")
def settings(config: AppConfig) -> ExportSettings:
    """Export settings for the synthetic source."""
    return ExportSettings(
        k=20,
        top_factors=config.business.top_factors,
        max_label_length=config.export.max_label_length,
        source_label=SOURCE,
        is_synthetic=True,
    )


@pytest.fixture(scope="module")
def batch(
    scoring: ScoringSet,
    model: TrainedModel,
    mapping: dict[str, FeatureMappingEntry],
    settings: ExportSettings,
) -> ScoringBatch:
    """The scored batch of the default date."""
    return score_accounts(scoring, model, mapping, settings)


def _written(batch: ScoringBatch, config: AppConfig, directory: Path, suffix: str) -> Path:
    """Write the batch to every default destination and return one file."""
    paths = write_batch(batch, directory, default_sinks(config.export))
    return next(path for path in paths if path.suffix == suffix)


def test_scoring_defaults_to_the_last_observation_date(
    dataset: Dataset, spec: GridSpec, scoring: ScoringSet
) -> None:
    """Without a date, the pipeline scores the most recent Monday it may."""
    assert scoring.date == observation_dates(dataset.events, spec)[-1]
    assert (scoring.grid["T0"] == scoring.date).all()


def test_scoring_covers_a_date_training_must_drop(
    training: TrainingSet, scoring: ScoringSet
) -> None:
    """On the scoring date nobody knows the outcome yet, which is the point."""
    assert scoring.date > training.grid["T0"].max()
    assert not scoring.grid.empty
    assert "y" not in scoring.grid.columns


def test_scoring_features_match_training_features_on_a_shared_date(
    dataset: Dataset, spec: GridSpec, training: TrainingSet
) -> None:
    """The model sees on Monday exactly what it learned from."""
    shared = training.grid["T0"].max()
    scored = build_scoring_set(dataset, spec, shared)
    rows = (training.grid["T0"] == shared).to_numpy()
    expected = training.features.loc[rows].set_index(training.grid.loc[rows, "client_id"])
    actual = scored.features.set_index(scored.grid["client_id"])
    pd.testing.assert_frame_equal(actual.sort_index(), expected.sort_index())


def test_only_active_accounts_old_enough_are_scored(
    dataset: Dataset, spec: GridSpec, scoring: ScoringSet
) -> None:
    """Scoring an account already gone, or too young, would mean nothing."""
    accounts = dataset.accounts.set_index("client_id").loc[scoring.grid["client_id"]]
    ended = accounts["date_resiliation"]
    assert (ended.isna() | (ended > scoring.date)).all()
    age = scoring.date - accounts["date_debut_contrat"]
    assert (age >= pd.Timedelta(days=spec.min_account_age_days)).all()


def test_a_scoring_date_without_timezone_is_refused(dataset: Dataset, spec: GridSpec) -> None:
    """A naive date is ambiguous by a whole timezone, enough to leak a day."""
    with pytest.raises(ValueError, match="timezone"):
        build_scoring_set(dataset, spec, pd.Timestamp("2025-01-06"))


def test_rows_follow_the_output_sort(batch: ScoringBatch) -> None:
    """Score, then revenue, then identifier: two runs rank the same accounts."""
    rows = batch.rows
    expected = rows.sort_values(
        ["score_brut_technique", "mrr", "client_id"],
        ascending=[False, False, True],
        kind="stable",
        ignore_index=True,
    )
    pd.testing.assert_frame_equal(rows.reset_index(drop=True), expected)
    assert rows["rang_priorite"].tolist() == list(range(1, len(rows) + 1))


def test_deciles_are_ordered_and_balanced(batch: ScoringBatch) -> None:
    """Decile 1 holds the highest scores, and deciles differ by one row at most."""
    deciles = batch.rows["decile_risque"].to_numpy(dtype="int64")
    assert deciles.min() == 1
    assert deciles.max() == 10
    assert (np.diff(deciles) >= 0).all()
    sizes = np.bincount(deciles)[1:]
    assert sizes.max() - sizes.min() <= 1


def test_risk_deciles_on_a_hand_made_case() -> None:
    """Twenty rows give two rows per decile."""
    expected = [decile for decile in range(1, 11) for _ in range(2)]
    assert risk_deciles(np.arange(1, 21), 20).tolist() == expected


def test_top_k_flags_the_head_of_the_list(batch: ScoringBatch, settings: ExportSettings) -> None:
    """The first K rows, and only them, are the week's calls."""
    flags = batch.rows["is_top_k"].to_numpy(dtype=bool)
    k = min(settings.k, len(flags))
    assert flags[:k].all()
    assert not flags[k:].any()


def test_every_row_carries_the_batch_and_the_model(
    batch: ScoringBatch, model: TrainedModel
) -> None:
    """Criterion 2 of lot 6: any row traces back to its run and its model."""
    rows = batch.rows
    assert (rows["batch_run_id"] == str(batch.batch_run_id)).all()
    assert (rows["model_version"] == model.metadata.model_version).all()


def test_the_batch_identity_depends_on_its_inputs_only() -> None:
    """Decision D20: same inputs, same identifier; any change, another one."""
    day = date(2025, 1, 6)
    first = batch_run_id("0.1.0-a", day, "digest")
    assert first == batch_run_id("0.1.0-a", day, "digest")
    assert first != batch_run_id("0.1.0-b", day, "digest")
    assert first != batch_run_id("0.1.0-a", date(2025, 1, 13), "digest")
    assert first != batch_run_id("0.1.0-a", day, "another digest")


def test_only_actionable_factors_take_a_slot(
    batch: ScoringBatch, mapping: dict[str, FeatureMappingEntry]
) -> None:
    """Decision D19: a salesperson can do nothing with the account age."""
    labels = batch.rows[list(FACTOR_COLUMNS)].to_numpy().ravel()
    assert any(labels), "no factor at all, the check would prove nothing"
    assert not any(label.startswith("[GENERAL]") for label in labels)
    assert {"mrr", "anciennete_jours"}.isdisjoint(actionable_origins(mapping))


def test_a_factor_count_outside_the_contract_is_refused(
    scoring: ScoringSet,
    model: TrainedModel,
    mapping: dict[str, FeatureMappingEntry],
    settings: ExportSettings,
) -> None:
    """The contract carries three factor columns, the configuration cannot say four."""
    with pytest.raises(ValueError, match="top_factors"):
        score_accounts(scoring, model, mapping, dataclasses.replace(settings, top_factors=4))


def test_the_contract_check_catches_every_breach(
    batch: ScoringBatch, settings: ExportSettings
) -> None:
    """A malformed export discovered in a spreadsheet is discovered too late."""
    rows = batch.rows
    limit = settings.max_label_length
    with pytest.raises(ValueError, match="columns"):
        validate_export(rows[list(reversed(EXPORT_COLUMNS))], limit)
    with pytest.raises(ValueError, match="breach"):
        validate_export(rows.assign(decile_risque=11), limit)
    with pytest.raises(ValueError, match="characters"):
        validate_export(rows.assign(facteur_risque_1="x" * (limit + 1)), limit)
    with pytest.raises(ValueError, match="rang_priorite"):
        validate_export(rows.assign(rang_priorite=rows["rang_priorite"].to_numpy()[::-1]), limit)


def test_two_runs_write_identical_files(
    dataset: Dataset,
    spec: GridSpec,
    model: TrainedModel,
    mapping: dict[str, FeatureMappingEntry],
    settings: ExportSettings,
    config: AppConfig,
    tmp_path: Path,
) -> None:
    """Criterion 1 of lot 6: the whole chain is recomputed twice, byte for byte."""
    written = []
    for run in ("first", "second"):
        scored = score_accounts(build_scoring_set(dataset, spec), model, mapping, settings)
        written.append(write_batch(scored, tmp_path / run, default_sinks(config.export)))
    assert len(written[0]) == 3
    for first, second in zip(written[0], written[1], strict=True):
        assert first.name == second.name
        assert first.read_bytes() == second.read_bytes(), f"{first.name} differs between runs"


def test_the_csv_reads_back_as_a_french_spreadsheet_would(
    batch: ScoringBatch, config: AppConfig, tmp_path: Path
) -> None:
    """Criterion 3 of lot 6, automated part: byte order mark, separator, decimal mark."""
    path = _written(batch, config, tmp_path, ".csv")
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "without a byte order mark Excel breaks accents"
    assert raw.decode("utf-8-sig").splitlines()[0] == ";".join(EXPORT_COLUMNS)

    back = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig", keep_default_na=False)
    assert back["score_brut_technique"].to_numpy() == pytest.approx(
        batch.rows["score_brut_technique"].to_numpy(dtype="float64")
    )
    for column in FACTOR_COLUMNS:
        assert back[column].tolist() == batch.rows[column].tolist()


def test_the_parquet_keeps_the_batch_identity(
    batch: ScoringBatch, config: AppConfig, tmp_path: Path
) -> None:
    """The source of truth says where it comes from, decision D2."""
    table = pq.read_table(_written(batch, config, tmp_path, ".parquet"))
    identity = json.loads(table.schema.metadata[PARQUET_METADATA_KEY])
    assert identity["batch_run_id"] == str(batch.batch_run_id)
    assert identity["is_synthetic"] is True
    assert tuple(table.column_names) == EXPORT_COLUMNS
    assert table.num_rows == len(batch.rows)


def test_the_json_carries_identity_and_rows(
    batch: ScoringBatch, config: AppConfig, tmp_path: Path
) -> None:
    """A dedicated front end could read the export without the pipeline, D15."""
    payload = json.loads(_written(batch, config, tmp_path, ".json").read_text(encoding="utf-8"))
    assert payload["row_count"] == len(payload["rows"]) == len(batch.rows)
    assert payload["is_synthetic"] is True
    assert tuple(payload["rows"][0]) == EXPORT_COLUMNS
    assert payload["rows"][0]["date_scoring"] == batch.date_scoring.isoformat()


class _MemorySink:
    """A destination that exists only in this test."""

    name = "memory"

    def __init__(self) -> None:
        self.received: list[ScoringBatch] = []

    def write(self, batch: ScoringBatch, directory: Path) -> Path:
        self.received.append(batch)
        return directory / self.name


def test_a_new_destination_needs_nothing_outside_its_own_class(
    batch: ScoringBatch, tmp_path: Path
) -> None:
    """Criterion 4 of lot 6: the pipeline takes any implementation of Sink."""
    sink = _MemorySink()
    written = write_batch(batch, tmp_path, [sink])
    assert len(sink.received) == 1
    assert sink.received[0] is batch
    assert written == [tmp_path / "memory"]


def test_an_empty_batch_still_writes_readable_files(
    dataset: Dataset,
    spec: GridSpec,
    model: TrainedModel,
    mapping: dict[str, FeatureMappingEntry],
    settings: ExportSettings,
    config: AppConfig,
    tmp_path: Path,
) -> None:
    """The interface of lot 7 must start on an empty export, so the export exists."""
    too_early = dataset.accounts["date_debut_contrat"].min() + pd.Timedelta(days=1)
    empty = score_accounts(build_scoring_set(dataset, spec, too_early), model, mapping, settings)
    assert empty.rows.empty

    paths = write_batch(empty, tmp_path, default_sinks(config.export))
    by_suffix = {path.suffix: path for path in paths}
    assert by_suffix[".csv"].read_bytes().decode("utf-8-sig").strip() == ";".join(EXPORT_COLUMNS)
    payload = json.loads(by_suffix[".json"].read_text(encoding="utf-8"))
    assert payload["rows"] == []
    assert payload["row_count"] == 0
    assert pq.read_table(by_suffix[".parquet"]).num_rows == 0


def test_the_most_recent_model_is_picked(model: TrainedModel, tmp_path: Path) -> None:
    """Without an explicit model, the latest training wins."""
    older = save_model(model, tmp_path)
    later = dataclasses.replace(
        model.metadata, model_version="0.0.0-later", created_at="2999-01-01T00:00:00+00:00"
    )
    newer = save_model(TrainedModel(classifier=model.classifier, metadata=later), tmp_path)
    assert older != newer
    assert latest_model_folder(tmp_path) == newer


def test_a_missing_model_is_reported(tmp_path: Path) -> None:
    """Scoring without a model says what to run first."""
    with pytest.raises(FileNotFoundError, match="train_model"):
        latest_model_folder(tmp_path / "absent")


def test_a_model_from_another_source_is_refused(model: TrainedModel) -> None:
    """A simulated model scoring real accounts would look legitimate, decision D2."""
    real = SourceDescription("kkbox", "KKBox", is_synthetic=False, horizon_days=30, embargo_days=30)
    with pytest.raises(ValueError, match="cannot score"):
        check_model_source(model, real)
    same = SourceDescription(
        "synthetic", SOURCE, is_synthetic=True, horizon_days=60, embargo_days=60
    )
    check_model_source(model, same)


def test_a_decimal_mark_equal_to_the_separator_is_refused(
    raw_config: dict[str, Any], write_yaml: Callable[[dict[str, Any]], Path]
) -> None:
    """A decimal number would split into two columns."""
    raw_config["export"]["csv_decimal"] = raw_config["export"]["csv_separator"]
    with pytest.raises(ConfigError, match="csv_decimal"):
        load_config(write_yaml(raw_config))
