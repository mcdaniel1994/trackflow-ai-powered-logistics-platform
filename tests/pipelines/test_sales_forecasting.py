"""Correctness and isolation tests for Engagement 6.5."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from importlib.util import resolve_name
from pathlib import Path

import numpy as np
import pytest

from process.sales_forecasting import (
    FEATURE_DEFINITIONS,
    FEATURE_NAMES,
    MAX_LAG,
    TEST_END,
    TEST_START,
    TRAIN_END,
    TRAIN_START,
    MetricError,
    SalesDataError,
    assert_causal_feature_contract,
    build_training_features,
    chronological_fold_indices,
    evaluate_chronological_cv,
    evaluate_test_metrics,
    feature_values,
    fit_estimator,
    k2_normality,
    load_sales_csv,
    mean_absolute_error,
    mean_squared_error,
    population_stability_index,
    recursive_ensemble_forecast,
    somers_d,
    temporal_split,
    validate_sales_rows,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPOSITORY_ROOT / "data" / "raw" / "trackflow_sales.csv"
GENERATOR = REPOSITORY_ROOT / "scripts" / "generate_trackflow_sales.py"
TRAINING_SCRIPT = REPOSITORY_ROOT / "scripts" / "train_sales_forecast.py"


@pytest.fixture(autouse=True)
def clean_pipeline_tables() -> None:
    """Override the pipeline suite's database fixture for these pure offline tests."""


@pytest.fixture(scope="module")
def sales_rows() -> tuple[object, ...]:
    return load_sales_csv(DATASET)


def test_temporal_split_is_exact_and_has_no_overlap(sales_rows: tuple[object, ...]) -> None:
    split = temporal_split(sales_rows)  # type: ignore[arg-type]
    assert len(split.train) == 96
    assert len(split.test) == 24
    assert split.train[0].month == TRAIN_START
    assert split.train[-1].month == TRAIN_END
    assert split.test[0].month == TEST_START
    assert split.test[-1].month == TEST_END
    assert set(split.train).isdisjoint(split.test)
    assert max(row.month for row in split.train) < min(row.month for row in split.test)


def test_feature_contract_excludes_contemporaneous_target_and_companions(
    sales_rows: tuple[object, ...],
) -> None:
    split = temporal_split(sales_rows)  # type: ignore[arg-type]
    assert_causal_feature_contract()
    assert FEATURE_NAMES == (
        "month_sin",
        "month_cos",
        "quarter",
        "is_peak_month",
        "is_february_trough",
        "time_index",
        "revenue_lag_1_eur",
        "revenue_lag_12_eur",
    )
    for definition in FEATURE_DEFINITIONS:
        if definition.source == "revenue_eur":
            assert definition.lag_months is not None and definition.lag_months >= 1
        assert definition.source not in {
            "shipments_processed",
            "avg_revenue_per_shipment_eur",
        }

    original = build_training_features(split.train)
    target_index = MAX_LAG
    changed_current = list(split.train)
    changed_current[target_index] = replace(
        changed_current[target_index],
        revenue_eur=changed_current[target_index].revenue_eur * 10,
        shipments_processed=changed_current[target_index].shipments_processed * 10,
        avg_revenue_per_shipment_eur=1.0,
    )
    changed = build_training_features(tuple(changed_current))
    np.testing.assert_array_equal(original.values[0], changed.values[0])
    assert original.targets[0] != changed.targets[0]
    assert original.values.shape == (84, 8)
    assert original.months[0].isoformat() == "2017-01-01"


def test_feature_lags_are_strictly_prior_and_tree_scaling_is_not_used(
    sales_rows: tuple[object, ...],
) -> None:
    split = temporal_split(sales_rows)  # type: ignore[arg-type]
    first = build_training_features(split.train)
    values = first.values[0]
    assert values[-2] == split.train[11].revenue_eur
    assert values[-1] == split.train[0].revenue_eur
    assert values[5] == 12

    with pytest.raises(SalesDataError, match="time index"):
        feature_values(split.train[12].month, 13, [row.revenue_eur for row in split.train[:12]])
    with pytest.raises(SalesDataError, match="12 prior"):
        feature_values(split.train[1].month, 1, [split.train[0].revenue_eur])
    with pytest.raises(SalesDataError, match="more than 12"):
        build_training_features(split.train[:12])
    with pytest.raises(SalesDataError, match="chronological"):
        build_training_features(tuple(reversed(split.train)))


def test_recursive_forecast_never_reads_observed_test_targets(
    sales_rows: tuple[object, ...],
) -> None:
    split = temporal_split(sales_rows)  # type: ignore[arg-type]
    features = build_training_features(split.train)
    model = fit_estimator(features)
    original = recursive_ensemble_forecast(model, split.train, split.test)
    altered_test = tuple(replace(row, revenue_eur=row.revenue_eur * 100) for row in split.test)
    altered = recursive_ensemble_forecast(model, split.train, altered_test)
    np.testing.assert_array_equal(original.point, altered.point)
    np.testing.assert_array_equal(original.per_tree, altered.per_tree)
    assert original.per_tree.shape == (400, 24)
    assert np.all(original.lower_p10 <= original.point)
    assert np.all(original.point <= original.upper_p90)

    unfitted = type(model)(**model.get_params())
    with pytest.raises(SalesDataError, match="fitted"):
        recursive_ensemble_forecast(unfitted, split.train, split.test)
    with pytest.raises(SalesDataError, match="chronological"):
        recursive_ensemble_forecast(model, split.test, split.train)


def test_fixed_seed_reproduces_predictions_and_metrics(sales_rows: tuple[object, ...]) -> None:
    split = temporal_split(sales_rows)  # type: ignore[arg-type]
    features = build_training_features(split.train)
    first_model = fit_estimator(features)
    second_model = fit_estimator(features)
    first = recursive_ensemble_forecast(first_model, split.train, split.test)
    second = recursive_ensemble_forecast(second_model, split.train, split.test)
    np.testing.assert_array_equal(first.per_tree, second.per_tree)

    actual = np.asarray([row.revenue_eur for row in split.test])
    first_metrics = evaluate_test_metrics(
        actual,
        first.point,
        training_predictions=first_model.predict(features.values),
    )
    second_metrics = evaluate_test_metrics(
        actual,
        second.point,
        training_predictions=second_model.predict(features.values),
    )
    assert first_metrics == second_metrics
    assert first_metrics.mse_eur_squared > 0
    assert 0 <= first_metrics.somers_d_gini <= 1


def test_binding_metric_definitions_and_edge_cases() -> None:
    assert mean_absolute_error([1, 2, 3], [1, 4, 3]) == pytest.approx(2 / 3)
    assert mean_squared_error([1, 2, 3], [1, 4, 3]) == pytest.approx(4 / 3)
    assert somers_d([1, 2, 3], [10, 20, 30]) == 1.0
    assert somers_d([1, 2, 3], [30, 20, 10]) == -1.0
    assert somers_d([1, 2, 3], [10, 10, 30]) == pytest.approx(2 / 3)
    assert population_stability_index(np.arange(100), np.arange(100)) == pytest.approx(0.0)
    assert population_stability_index(np.arange(100), np.arange(100) + 1000) > 0.25

    statistic, p_value = k2_normality([-3, -2, -1, -0.5, 0.5, 1, 2, 3])
    assert np.isfinite(statistic)
    assert 0 <= p_value <= 1
    with pytest.raises(MetricError, match="at least 8"):
        k2_normality([1, 2, 3])
    with pytest.raises(MetricError, match="identical shapes"):
        mean_squared_error([1], [1, 2])
    with pytest.raises(MetricError, match="distinct actual"):
        somers_d([1, 1], [1, 2])
    with pytest.raises(MetricError, match="at least two"):
        population_stability_index([1, 2], [1, 2], bins=1)
    with pytest.raises(MetricError, match="epsilon"):
        population_stability_index([1, 2], [1, 2], epsilon=0)
    with pytest.raises(MetricError, match="finite"):
        mean_squared_error([1, np.nan], [1, 2])


def test_chronological_cross_validation_preserves_order_and_training_boundary(
    sales_rows: tuple[object, ...],
) -> None:
    split = temporal_split(sales_rows)  # type: ignore[arg-type]
    indices = chronological_fold_indices(len(split.train))
    assert len(indices) == 5
    assert [len(train) for train, _ in indices] == [16, 32, 48, 64, 80]
    assert [len(validation) for _, validation in indices] == [16] * 5

    previous_validation_end = -1
    for train_indices, validation_indices in indices:
        assert train_indices == tuple(sorted(train_indices))
        assert validation_indices == tuple(sorted(validation_indices))
        assert set(train_indices).isdisjoint(validation_indices)
        assert max(train_indices) < min(validation_indices)
        assert min(validation_indices) > previous_validation_end
        assert max(validation_indices) < len(split.train)
        assert split.train[max(validation_indices)].month <= TRAIN_END
        previous_validation_end = max(validation_indices)

    with pytest.raises(SalesDataError, match="at least five"):
        chronological_fold_indices(len(split.train), n_splits=4)
    with pytest.raises(SalesDataError, match="not enough"):
        chronological_fold_indices(17)


def test_chronological_evaluation_is_fold_local_and_reports_population_spread(
    sales_rows: tuple[object, ...],
) -> None:
    split = temporal_split(sales_rows)  # type: ignore[arg-type]
    evaluation = evaluate_chronological_cv(split.train)
    assert evaluation.standard_deviation_convention == "population_ddof_0"
    assert [fold.train_post_lag_rows for fold in evaluation.folds] == [4, 20, 36, 52, 68]
    assert [fold.validation_rows for fold in evaluation.folds] == [16] * 5
    validation_rmse = np.asarray(
        [fold.validation_rmse_eur for fold in evaluation.folds],
        dtype=np.float64,
    )
    assert evaluation.validation_rmse.mean_eur == pytest.approx(
        float(np.mean(validation_rmse))
    )
    assert evaluation.validation_rmse.standard_deviation_eur == pytest.approx(
        float(np.std(validation_rmse, ddof=0))
    )
    payload = evaluation.as_dict()
    assert payload["standard_deviation_convention"] == "population_ddof_0"
    assert len(payload["folds"]) == 5  # type: ignore[arg-type]
    assert payload["folds"][0]["train_start"] == "2016-01-01"  # type: ignore[index]

    first_train_indices, first_validation_indices = chronological_fold_indices(
        len(split.train)
    )[0]
    first_train = tuple(split.train[index] for index in first_train_indices)
    first_validation = tuple(split.train[index] for index in first_validation_indices)
    features = build_training_features(first_train)
    model = fit_estimator(features)
    original = recursive_ensemble_forecast(model, first_train, first_validation)
    altered_validation = tuple(
        replace(row, revenue_eur=row.revenue_eur * 100)
        for row in first_validation
    )
    altered = recursive_ensemble_forecast(model, first_train, altered_validation)
    np.testing.assert_array_equal(original.point, altered.point)


def _read_csv_records(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("empty", "null or empty"),
        ("bad_month", "YYYY-MM-01"),
        ("bad_float", "must be numeric"),
        ("negative_float", "positive and finite"),
        ("bad_int", "must be an integer"),
        ("negative_int", "positive integer"),
        ("bad_market", "consolidated"),
        ("inconsistent", "internally inconsistent"),
        ("duplicate_month", "unique, ordered, gap-free"),
    ],
)
def test_malformed_input_fails_loudly(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    fieldnames, records = _read_csv_records(DATASET)
    if mutation == "empty":
        records[0]["revenue_eur"] = ""
    elif mutation == "bad_month":
        records[0]["month"] = "2016-01-02"
    elif mutation == "bad_float":
        records[0]["revenue_eur"] = "not-a-number"
    elif mutation == "negative_float":
        records[0]["revenue_eur"] = "-1"
    elif mutation == "bad_int":
        records[0]["shipments_processed"] = "1.5"
    elif mutation == "negative_int":
        records[0]["shipments_processed"] = "-1"
    elif mutation == "bad_market":
        records[0]["market"] = "us"
    elif mutation == "inconsistent":
        records[0]["avg_revenue_per_shipment_eur"] = "999"
    elif mutation == "duplicate_month":
        records[1]["month"] = records[0]["month"]
    output = tmp_path / "bad.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    with pytest.raises(SalesDataError, match=message):
        load_sales_csv(output)


def test_wrong_schema_short_series_and_bad_partition_are_rejected(tmp_path: Path) -> None:
    wrong_schema = tmp_path / "schema.csv"
    wrong_schema.write_text("month,revenue_eur\n2016-01-01,1\n", encoding="utf-8")
    with pytest.raises(SalesDataError, match="expected columns"):
        load_sales_csv(wrong_schema)
    with pytest.raises(SalesDataError, match="expected 120"):
        validate_sales_rows(())

    rows = load_sales_csv(DATASET)
    with pytest.raises(SalesDataError, match="expected 120"):
        temporal_split(rows[:-1])
    with pytest.raises(SalesDataError, match="cannot read"):
        load_sales_csv(tmp_path / "missing.csv")


def test_generator_default_validation_and_regeneration_are_byte_identical(
    tmp_path: Path,
) -> None:
    checked = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0
    assert "validation: OK" in checked.stdout

    regenerated = tmp_path / "regenerated.csv"
    generated = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(regenerated)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert generated.returncode == 0
    assert regenerated.read_bytes() == DATASET.read_bytes()

    malformed = tmp_path / "malformed.csv"
    malformed.write_text("wrong\nvalue\n", encoding="utf-8")
    rejected = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--output",
            str(malformed),
            "--check",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 1
    assert "validation error" in rejected.stdout

    fieldnames, records = _read_csv_records(DATASET)
    for field, invalid_value, expected_message in (
        ("revenue_eur", "nan", "positive and finite"),
        ("avg_revenue_per_shipment_eur", "nan", "positive and finite"),
        ("month", "2016-01-02", "month sequence"),
    ):
        mutated = [record.copy() for record in records]
        mutated[0][field] = invalid_value
        invalid = tmp_path / f"invalid-{field}.csv"
        with invalid.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(mutated)
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--output",
                str(invalid),
                "--check",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert expected_message in result.stdout


def test_training_entrypoint_writes_complete_versioned_artifact_contract(
    tmp_path: Path,
) -> None:
    first = subprocess.run(
        [
            sys.executable,
            str(TRAINING_SCRIPT),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stdout + first.stderr
    expected = {
        "sales_forecast_model.v1.pkl",
        "sales_forecast_predictions.v1.csv",
        "sales_forecast_predictions.v1.png",
        "sales_forecast_metrics.v1.json",
        "sales_forecast_model_card.v1.md",
        "sales_forecast_manifest.v1.json",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected

    manifest = json.loads((tmp_path / "sales_forecast_manifest.v1.json").read_text())
    assert manifest["random_seed"] == 42
    assert manifest["forecast_protocol"] == "strict_origin_time_recursive_per_tree"
    assert manifest["split"] == {
        "test_end": "2025-12-01",
        "test_rows": 24,
        "test_start": "2024-01-01",
        "train_end": "2023-12-01",
        "train_post_lag_rows": 84,
        "train_source_rows": 96,
        "train_start": "2016-01-01",
    }
    assert manifest["prediction_band"]["meaning"] == "ensemble_spread_not_calibrated_interval"
    assert len(manifest["artifact_hashes_sha256"]) == 5
    metrics = json.loads((tmp_path / "sales_forecast_metrics.v1.json").read_text())
    assert set(metrics["metrics"]) == {
        "k2_p_value",
        "k2_statistic",
        "mse_eur_squared",
        "psi_predicted_revenue",
        "rmse_eur",
        "rmse_percent_mean_test_revenue",
        "somers_d_gini",
    }
    assert len((tmp_path / "sales_forecast_predictions.v1.csv").read_text().splitlines()) == 25
    assert (tmp_path / "sales_forecast_predictions.v1.png").stat().st_size > 10_000

    refused = subprocess.run(
        [sys.executable, str(TRAINING_SCRIPT), "--output-dir", str(tmp_path)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 1
    assert "pass --force" in refused.stdout


def test_evaluation_entrypoint_writes_reproducible_formal_evidence(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(TRAINING_SCRIPT),
            "--output-dir",
            str(tmp_path),
            "--evaluate",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    expected = {
        "evaluation_report.md",
        "sales_forecast_evaluation.v1.json",
        "sales_forecast_evaluation_manifest.v1.json",
        "sales_forecast_learning_curve.v1.png",
        "sales_forecast_manifest.v1.json",
        "sales_forecast_metrics.v1.json",
        "sales_forecast_model.v1.pkl",
        "sales_forecast_model_card.v1.md",
        "sales_forecast_predictions.v1.csv",
        "sales_forecast_predictions.v1.png",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected

    evaluation = json.loads(
        (tmp_path / "sales_forecast_evaluation.v1.json").read_text()
    )
    assert evaluation["diagnosis"] == "overfitting"
    assert evaluation["training_partition_only"]["holdout_used_for_diagnosis"] is False
    assert len(evaluation["cross_validation"]["folds"]) == 5
    assert (
        evaluation["cross_validation"]["standard_deviation_convention"]
        == "population_ddof_0"
    )
    report = (tmp_path / "evaluation_report.md").read_text()
    for required in (
        "**Classification: overfitting.**",
        "Validation RMSE",
        "Corrective action",
        "generated rather than observed",
        "not a calibrated",
        "not approved for serving",
        "Ticket answers",
    ):
        assert required in report
    assert (tmp_path / "sales_forecast_learning_curve.v1.png").stat().st_size > 10_000

    evaluation_manifest = json.loads(
        (tmp_path / "sales_forecast_evaluation_manifest.v1.json").read_text()
    )
    assert evaluation_manifest["phase"] == "6.5.b"
    assert len(evaluation_manifest["artifact_hashes_sha256"]) == 3
    phase_a_manifest_hash = hashlib.sha256(
        (tmp_path / "sales_forecast_manifest.v1.json").read_bytes()
    ).hexdigest()
    assert (
        evaluation_manifest["accepted_phase_6_5_a_manifest_sha256"]
        == phase_a_manifest_hash
    )
    first_bytes = {
        path.name: path.read_bytes()
        for path in tmp_path.iterdir()
        if path.is_file()
    }

    refused = subprocess.run(
        [
            sys.executable,
            str(TRAINING_SCRIPT),
            "--output-dir",
            str(tmp_path),
            "--evaluate",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 1
    assert "pass --force" in refused.stdout

    reproduced = subprocess.run(
        [
            sys.executable,
            str(TRAINING_SCRIPT),
            "--output-dir",
            str(tmp_path),
            "--evaluate",
            "--force",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert reproduced.returncode == 0, reproduced.stdout + reproduced.stderr
    assert {
        path.name: path.read_bytes()
        for path in tmp_path.iterdir()
        if path.is_file()
    } == first_bytes


def _module_source(module_name: str) -> Path | None:
    roots = {
        "central_api": REPOSITORY_ROOT / "services" / "central-api",
        "pipelines": REPOSITORY_ROOT / "data",
        "process": REPOSITORY_ROOT / "data",
        "scripts": REPOSITORY_ROOT / "services" / "central-api",
    }
    root = roots.get(module_name.partition(".")[0])
    if root is None:
        return None
    candidate = root.joinpath(*module_name.split("."))
    module_file = candidate.with_suffix(".py")
    if module_file.is_file():
        return module_file
    package_file = candidate / "__init__.py"
    return package_file if package_file.is_file() else None


def _source_imports(module_name: str, source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    package = module_name if source.name == "__init__.py" else module_name.rpartition(".")[0]
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            relative_name = f"{'.' * node.level}{node.module or ''}"
            try:
                base = resolve_name(relative_name, package)
            except (ImportError, ValueError):
                continue
        else:
            base = node.module or ""
        if base:
            imported.add(base)
        for alias in node.names:
            candidate = f"{base}.{alias.name}" if base else alias.name
            if _module_source(candidate) is not None:
                imported.add(candidate)
    return imported


def test_production_import_graph_excludes_forecasting_and_ml_packages() -> None:
    forbidden = {
        "matplotlib",
        "numpy",
        "process.sales_forecasting",
        "scipy",
        "sklearn",
    }
    pending = [
        "central_api.main",
        "pipelines.business_performance.worker",
        "scripts.maintenance_worker",
    ]
    visited: set[str] = set()
    violations: list[str] = []
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        visited.add(module_name)
        source = _module_source(module_name)
        assert source is not None, f"production root {module_name} is not importable from repository sources"
        for imported_name in _source_imports(module_name, source):
            if any(
                imported_name == blocked or imported_name.startswith(f"{blocked}.")
                for blocked in forbidden
            ):
                violations.append(
                    f"{source.relative_to(REPOSITORY_ROOT)} imports {imported_name}"
                )
            elif _module_source(imported_name) is not None:
                pending.append(imported_name)

    assert len(visited) > 20, "production import traversal was unexpectedly shallow"
    assert violations == []
