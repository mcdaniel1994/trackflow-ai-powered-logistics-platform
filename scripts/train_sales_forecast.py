"""Train the offline Engagement 6.5.a Random Forest and write versioned artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pickle
import platform
import tempfile
from datetime import date
from importlib.metadata import version
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from process.sales_forecasting import (
    CrossValidationEvaluation,
    ESTIMATOR_PARAMETERS,
    FEATURE_DEFINITIONS,
    FEATURE_NAMES,
    RANDOM_SEED,
    MetricError,
    SalesDataError,
    build_training_features,
    evaluate_test_metrics,
    evaluate_chronological_cv,
    fit_estimator,
    load_sales_csv,
    recursive_ensemble_forecast,
    temporal_split,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPOSITORY_ROOT / "data" / "raw" / "trackflow_sales.csv"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "data" / "eval"
ARTIFACT_VERSION = 1
ARTIFACT_NAMES = (
    "sales_forecast_model.v1.pkl",
    "sales_forecast_predictions.v1.csv",
    "sales_forecast_predictions.v1.png",
    "sales_forecast_metrics.v1.json",
    "sales_forecast_model_card.v1.md",
    "sales_forecast_manifest.v1.json",
)
EVALUATION_ARTIFACT_NAMES = (
    "sales_forecast_evaluation.v1.json",
    "sales_forecast_learning_curve.v1.png",
    "evaluation_report.md",
    "sales_forecast_evaluation_manifest.v1.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_predictions(
    path: Path,
    months: tuple[date, ...],
    actual: np.ndarray[Any, np.dtype[np.float64]],
    predicted: np.ndarray[Any, np.dtype[np.float64]],
    lower: np.ndarray[Any, np.dtype[np.float64]],
    upper: np.ndarray[Any, np.dtype[np.float64]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ("month", "actual_revenue_eur", "predicted_revenue_eur", "ensemble_p10_eur", "ensemble_p90_eur")
        )
        for month, actual_value, prediction, p10, p90 in zip(
            months, actual, predicted, lower, upper, strict=True
        ):
            writer.writerow(
                (
                    month.isoformat(),
                    f"{actual_value:.2f}",
                    f"{prediction:.2f}",
                    f"{p10:.2f}",
                    f"{p90:.2f}",
                )
            )


def _write_chart(
    path: Path,
    months: tuple[date, ...],
    actual: np.ndarray[Any, np.dtype[np.float64]],
    predicted: np.ndarray[Any, np.dtype[np.float64]],
    lower: np.ndarray[Any, np.dtype[np.float64]],
    upper: np.ndarray[Any, np.dtype[np.float64]],
) -> None:
    figure, axis = plt.subplots(figsize=(12, 6.75))
    month_numbers = np.asarray(
        mdates.date2num(months),  # type: ignore[no-untyped-call]
        dtype=np.float64,
    )
    axis.plot(
        month_numbers,
        actual,
        color="#17324d",
        linewidth=2.2,
        marker="o",
        label="Actual revenue",
    )
    axis.plot(
        month_numbers,
        predicted,
        color="#d2691e",
        linewidth=2.2,
        marker="o",
        label="Strict recursive prediction",
    )
    axis.fill_between(
        month_numbers,
        lower,
        upper,
        color="#d2691e",
        alpha=0.22,
        label="Random Forest ensemble spread (P10–P90)",
    )
    axis.xaxis_date()
    axis.set_title("TrackFlow monthly revenue — 2024–2025 holdout")
    axis.set_xlabel("Month")
    axis.set_ylabel("Revenue (EUR)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="upper left")
    figure.text(
        0.5,
        0.01,
        "The shaded range is internal tree disagreement, not a calibrated prediction interval.",
        ha="center",
        fontsize=9,
    )
    figure.autofmt_xdate()
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(path, dpi=160, metadata={"Date": None})
    plt.close(figure)


def _write_learning_curve(
    path: Path,
    evaluation: CrossValidationEvaluation,
) -> None:
    source_rows = [fold.train_source_rows for fold in evaluation.folds]
    figure, axis = plt.subplots(figsize=(11, 6.5))
    axis.plot(
        source_rows,
        [fold.train_rmse_eur for fold in evaluation.folds],
        color="#17324d",
        linewidth=2.2,
        marker="o",
        label="Training RMSE",
    )
    axis.plot(
        source_rows,
        [fold.validation_rmse_eur for fold in evaluation.folds],
        color="#d2691e",
        linewidth=2.2,
        marker="o",
        label="Next-window validation RMSE",
    )
    axis.plot(
        source_rows,
        [fold.train_mae_eur for fold in evaluation.folds],
        color="#17324d",
        linewidth=1.5,
        linestyle="--",
        marker="s",
        alpha=0.75,
        label="Training MAE",
    )
    axis.plot(
        source_rows,
        [fold.validation_mae_eur for fold in evaluation.folds],
        color="#d2691e",
        linewidth=1.5,
        linestyle="--",
        marker="s",
        alpha=0.75,
        label="Next-window validation MAE",
    )
    axis.set_title("TrackFlow sales forecast — chronological learning curve")
    axis.set_xlabel("Chronological training-prefix source rows")
    axis.set_ylabel("Error (EUR)")
    axis.set_xticks(source_rows)
    axis.grid(alpha=0.25)
    axis.legend(loc="upper right")
    figure.text(
        0.5,
        0.01,
        "Each validation point is the next 16 months; the 2024–2025 holdout is never used.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(path, dpi=160, metadata={"Date": None})
    plt.close(figure)


def _psi_band(value: float) -> str:
    if value < 0.10:
        return "stable"
    if value <= 0.25:
        return "moderate shift"
    return "significant shift"


def _model_card(metrics: dict[str, float], train_rows: int) -> str:
    return f"""# TrackFlow Sales Forecast — Phase 6.5.a Model Card

## Scope and provenance

This is an offline feasibility artifact, not a production forecast or serving contract. The source
CSV is generated rather than observed. The owner approved that deviation because the assignment's
claimed input file did not exist and TrackFlow's production data has no revenue dimension. The
deterministic generator is `scripts/generate_trackflow_sales.py` and uses seed 42. Generated,
strongly seasonal data is easier to learn than real revenue, so these results are optimistic.

## Model decision

Random Forest was selected over XGBoost for three predeclared reasons: only {train_rows} post-lag
training observations are available; independent bagged trees are easier to explain to Finance;
and per-tree disagreement provides the requested variability band without another modelling
assumption. Hyperparameters were fixed before the holdout was inspected, with no Phase 6.5.a tuning
budget. Tree ensembles are scale-invariant, so no meaningless scaling transform was fitted.

## Forecast protocol and features

The model trains only on 2016-01 through 2023-12 and forecasts all 24 months from the 2023-12
origin. Each tree recursively supplies its own future lag values; no observed 2024–2025 revenue,
shipment count, or average revenue per shipment enters any test feature.

Features are cyclic month, quarter, peak/trough flags, a monotonic time index, and revenue lags at
1 and 12 months. Calendar values are known in advance; both revenue lags are strictly prior-period
values. Same-month `shipments_processed` and `avg_revenue_per_shipment_eur` are excluded because
they definitionally reveal the target.

## Holdout metrics

- MSE: {metrics["mse_eur_squared"]:,.2f} EUR².
- RMSE: {metrics["rmse_eur"]:,.2f} EUR, or
  {metrics["rmse_percent_mean_test_revenue"]:.2f}% of mean monthly test revenue. RMSE is the
  dimensionally meaningful percentage substitute for MSE.
- PSI over predicted revenue: {metrics["psi_predicted_revenue"]:.4f}
  ({_psi_band(metrics["psi_predicted_revenue"])}). Expected is the in-sample training-prediction
  distribution; actual is the strict recursive test-prediction distribution; ten quantile bins
  come from training only. This comparison spans earlier training years against later, growing test
  years, so a large value can reflect the known trend and bounded tree extrapolation rather than an
  unexpected regime change. The consolidated-only dataset cannot measure an LA/ZGZ volume-mix
  shift, so no geographic interpretation is claimed.
- Continuous-target Gini (Somers' D):
  {metrics["somers_d_gini"]:.4f}. This is
  `(concordant - discordant) / comparable actual pairs` and measures rank ordering.
- D'Agostino–Pearson K² on 24 test residuals:
  statistic {metrics["k2_statistic"]:.4f}, p-value {metrics["k2_p_value"]:.4f}. This is a
  residual-structure diagnostic, not accuracy; n=24 gives it low power.

A low MSE alone cannot establish ranking quality, distribution stability, or whether residuals
retain unmodelled structure. The chart's P10–P90 range is ensemble spread, not a calibrated
confidence or prediction interval.
"""


def _fold_table(evaluation: CrossValidationEvaluation) -> str:
    lines = [
        "| Fold | Train source / post-lag | Validation | Train dates | Validation dates | "
        "Train MAE / RMSE | Validation MAE / RMSE |",
        "|---:|---:|---:|---|---|---:|---:|",
    ]
    for fold in evaluation.folds:
        lines.append(
            f"| {fold.fold} | {fold.train_source_rows} / {fold.train_post_lag_rows} | "
            f"{fold.validation_rows} | {fold.train_start.isoformat()} → "
            f"{fold.train_end.isoformat()} | {fold.validation_start.isoformat()} → "
            f"{fold.validation_end.isoformat()} | {fold.train_mae_eur:,.0f} / "
            f"{fold.train_rmse_eur:,.0f} EUR | {fold.validation_mae_eur:,.0f} / "
            f"{fold.validation_rmse_eur:,.0f} EUR |"
        )
    return "\n".join(lines)


def _evaluation_report(
    evaluation: CrossValidationEvaluation,
    holdout_metrics: dict[str, float],
    *,
    dataset_hash: str,
) -> str:
    first = evaluation.folds[0]
    last = evaluation.folds[-1]
    return f"""# TrackFlow Sales Forecast — Formal Evaluation

## Decision

**Classification: overfitting.** Training RMSE falls from {first.train_rmse_eur:,.0f} EUR on the
smallest chronological prefix to {last.train_rmse_eur:,.0f} EUR on the largest, while the
next-window validation RMSE does not converge: it ranges from
{min(fold.validation_rmse_eur for fold in evaluation.folds):,.0f} to
{max(fold.validation_rmse_eur for fold in evaluation.folds):,.0f} EUR and ends at
{last.validation_rmse_eur:,.0f} EUR. The final temporal generalization gap is
{last.validation_rmse_eur - last.train_rmse_eur:,.0f} EUR. The curves therefore show increasingly
good in-sample fit without a matching improvement on later months.

The suspected root cause is specific: the Random Forest fits absolute revenue levels and absolute
lag values well inside the observed range, but trees cannot extrapolate the generator's continuing
compound trend beyond learned leaf values. **Corrective action:** change the model target to
year-over-year revenue growth (`revenue_t / revenue_t-12 - 1`), forecast that stationary quantity
with the same chronological protocol, and recursively reconstruct revenue levels. This directly
addresses bounded absolute-level extrapolation; it is not a generic request for more data or model
complexity.

## Dataset, split, and model

The dataset is [generated, not observed](../raw/trackflow_sales.csv), with SHA-256
`{dataset_hash}`. Its [standard-library generator](../../scripts/generate_trackflow_sales.py) uses
seed 42. The owner approved generation because the assignment's claimed input was absent and
TrackFlow production has no revenue dimension.

The fixed Random Forest was selected over XGBoost because only 96 training months (84 after lag
warm-up) exist, bagging is straightforward to explain to Finance, and there was no responsible
holdout-driven tuning budget. Features are calendar cycle, quarter, peak/trough flags, monotonic
time index, and strictly prior revenue lags 1 and 12. No same-month target, shipment count, or
average-revenue companion enters a feature. The 2024–2025 holdout remains untouched by the
cross-validation and learning-curve diagnosis.

## Five-fold chronological cross-validation

`TimeSeriesSplit(n_splits=5)` creates expanding training prefixes followed by five disjoint,
ordered 16-month validation windows. Feature construction and model fitting restart inside every
fold; validation is forecast recursively from that fold's origin. No fold shuffles, overlaps, or
reaches the 2024–2025 holdout.

{_fold_table(evaluation)}

Because the five folds are the complete predeclared evaluation set, variability uses population
standard deviation (`ddof=0`), not a sample estimate:

- Training MAE: **{evaluation.train_mae.mean_eur:,.0f} ±
  {evaluation.train_mae.standard_deviation_eur:,.0f} EUR**.
- Training RMSE: **{evaluation.train_rmse.mean_eur:,.0f} ±
  {evaluation.train_rmse.standard_deviation_eur:,.0f} EUR**.
- Validation MAE: **{evaluation.validation_mae.mean_eur:,.0f} ±
  {evaluation.validation_mae.standard_deviation_eur:,.0f} EUR**.
- Validation RMSE: **{evaluation.validation_rmse.mean_eur:,.0f} ±
  {evaluation.validation_rmse.standard_deviation_eur:,.0f} EUR**.

The 16-month validation windows are small, so the spread is material rather than noise to hide.
Validation RMSE has a coefficient of variation of
{evaluation.validation_rmse.standard_deviation_eur / evaluation.validation_rmse.mean_eur * 100:.1f}%.
Performance across temporal partitions is therefore **not stable enough for operational use**.

RMSE is the primary business metric because large peak-season misses can create disproportionate
warehouse staffing and capacity risk; squaring errors makes those misses visible. MAE remains the
companion metric because it expresses the typical monthly miss directly in EUR and prevents one
large month from being mistaken for routine performance. Formally,
`MAE = mean(|actual - predicted|)` and `RMSE = sqrt(mean((actual - predicted)^2))`.

![Chronological learning curve](sales_forecast_learning_curve.v1.png)

The relative pattern—not an absolute error threshold—drives the diagnosis: training errors become
low and remain low as the prefix grows, while validation errors oscillate and finish far above the
training curve. The two curves do not converge.

## Accepted holdout diagnostics

The untouched 2024–2025 result remains:

- MSE: {holdout_metrics["mse_eur_squared"]:,.2f} EUR²; RMSE:
  {holdout_metrics["rmse_eur"]:,.2f} EUR
  ({holdout_metrics["rmse_percent_mean_test_revenue"]:.2f}% of mean holdout revenue).
- PSI over predicted revenue: {holdout_metrics["psi_predicted_revenue"]:.4f}.
- Continuous-target Gini / Somers' D: {holdout_metrics["somers_d_gini"]:.4f}.
- D'Agostino–Pearson K²: {holdout_metrics["k2_statistic"]:.4f},
  `p = {holdout_metrics["k2_p_value"]:.6f}`.

MSE is mean squared error. PSI compares training-prediction and recursive-test-prediction
distributions using training-derived bins; it does not measure LA/Zaragoza mix because every row is
`consolidated`. Somers' D measures rank concordance over comparable actual pairs. K² tests residual
normality and is not an accuracy score; 24 residuals give it limited power.

The specification anticipated little or no PSI because the generator has no regime change, but the
selected predicted-revenue PSI is **significant**, not stable. That anticipation is wrong for this
subject: later generated revenue levels plus bounded tree extrapolation shift the prediction
distribution. This is still not evidence of a real-world regime change or model robustness.

## Required honesty and scope limits

- The data is generated rather than observed; deterministic trend and seasonality are easier to
  learn than real revenue, so every reported error is optimistic relative to production behavior.
- The generator contains no unexpected regime change. Whether PSI appears stable or significant,
  it describes this generator/model pairing and does not demonstrate robustness.
- Only 96 source training months exist, and the five validation windows contain 16 months each.
  Those sizes bound every conclusion.
- The P10–P90 band in the prediction chart is internal tree disagreement, not a calibrated
  confidence or prediction interval.
- This is an offline analysis artifact. It is not approved for serving, Finance forecasts,
  warehouse staffing, or any production decision.

## Ticket answers

1. **Fit diagnosis:** overfitting, evidenced by a persistent and widening temporal
   train/validation gap rather than an arbitrary error threshold.
2. **Partition stability:** not stable; validation RMSE is
   {evaluation.validation_rmse.mean_eur:,.0f} ±
   {evaluation.validation_rmse.standard_deviation_eur:,.0f} EUR across five small chronological
   folds.
3. **Corrective action:** forecast year-over-year revenue growth and reconstruct levels
   recursively, targeting the absolute-level extrapolation failure directly.
"""


def _refuse_ambiguous_output(output_dir: Path, *, force: bool) -> None:
    existing = [name for name in ARTIFACT_NAMES if (output_dir / name).exists()]
    if existing and not force:
        raise SalesDataError(
            "forecast artifacts already exist; pass --force to replace the complete versioned set"
        )
    if existing and len(existing) != len(ARTIFACT_NAMES):
        raise SalesDataError(
            "partial forecast artifact set detected; remove or restore it before retraining"
        )


def evaluate(
    dataset: Path,
    output_dir: Path,
    holdout_metrics: dict[str, float],
    *,
    force: bool = False,
) -> dict[str, object]:
    """Publish the Phase 6.5.b evaluation artifacts without changing the holdout."""
    existing = [
        name for name in EVALUATION_ARTIFACT_NAMES if (output_dir / name).exists()
    ]
    if existing and not force:
        raise SalesDataError(
            "evaluation artifacts already exist; pass --force to replace the complete set"
        )
    if existing and len(existing) != len(EVALUATION_ARTIFACT_NAMES):
        raise SalesDataError(
            "partial evaluation artifact set detected; remove or restore it before evaluation"
        )

    rows = load_sales_csv(dataset)
    split = temporal_split(rows)
    cross_validation = evaluate_chronological_cv(split.train)
    evaluation_payload: dict[str, object] = {
        "schema_version": ARTIFACT_VERSION,
        "training_partition_only": {
            "start": split.train[0].month.isoformat(),
            "end": split.train[-1].month.isoformat(),
            "source_rows": len(split.train),
            "holdout_start": split.test[0].month.isoformat(),
            "holdout_end": split.test[-1].month.isoformat(),
            "holdout_used_for_diagnosis": False,
        },
        "cross_validation": cross_validation.as_dict(),
        "primary_metric": {
            "name": "rmse_eur",
            "reason": "large peak-season misses create disproportionate staffing and capacity risk",
        },
        "diagnosis": "overfitting",
        "suspected_root_cause": "bounded_tree_extrapolation_on_absolute_revenue_levels",
        "corrective_action": "forecast_year_over_year_growth_then_recursively_reconstruct_revenue",
    }

    with tempfile.TemporaryDirectory(
        prefix=".sales-forecast-evaluation-",
        dir=output_dir,
    ) as staging_raw:
        staging = Path(staging_raw)
        evaluation_path = staging / EVALUATION_ARTIFACT_NAMES[0]
        _write_json(evaluation_path, evaluation_payload)
        learning_curve_path = staging / EVALUATION_ARTIFACT_NAMES[1]
        _write_learning_curve(learning_curve_path, cross_validation)
        report_path = staging / EVALUATION_ARTIFACT_NAMES[2]
        report_path.write_text(
            _evaluation_report(
                cross_validation,
                holdout_metrics,
                dataset_hash=_sha256(dataset),
            ),
            encoding="utf-8",
        )
        artifact_hashes = {
            path.name: _sha256(path)
            for path in (evaluation_path, learning_curve_path, report_path)
        }
        evaluation_manifest_path = staging / EVALUATION_ARTIFACT_NAMES[3]
        _write_json(
            evaluation_manifest_path,
            {
                "schema_version": ARTIFACT_VERSION,
                "phase": "6.5.b",
                "dataset_sha256": _sha256(dataset),
                "accepted_phase_6_5_a_manifest_sha256": _sha256(
                    output_dir / "sales_forecast_manifest.v1.json"
                ),
                "random_seed": RANDOM_SEED,
                "artifact_hashes_sha256": artifact_hashes,
            },
        )
        for name in EVALUATION_ARTIFACT_NAMES[:-1]:
            os.replace(staging / name, output_dir / name)
        os.replace(
            evaluation_manifest_path,
            output_dir / evaluation_manifest_path.name,
        )
    return evaluation_payload


def train(dataset: Path, output_dir: Path, *, force: bool = False) -> dict[str, float]:
    """Train once and publish a complete manifest-last artifact set."""
    output_dir.mkdir(parents=True, exist_ok=True)
    _refuse_ambiguous_output(output_dir, force=force)

    rows = load_sales_csv(dataset)
    split = temporal_split(rows)
    training = build_training_features(split.train)
    model = fit_estimator(training)
    forecast = recursive_ensemble_forecast(model, split.train, split.test)
    actual = np.asarray([row.revenue_eur for row in split.test], dtype=np.float64)
    training_predictions = np.asarray(model.predict(training.values), dtype=np.float64)
    metrics = evaluate_test_metrics(
        actual, forecast.point, training_predictions=training_predictions
    ).as_dict()

    with tempfile.TemporaryDirectory(prefix=".sales-forecast-", dir=output_dir) as staging_raw:
        staging = Path(staging_raw)
        model_path = staging / ARTIFACT_NAMES[0]
        with model_path.open("wb") as handle:
            # This pickle is a trusted local build artifact. It must never be loaded from
            # an untrusted source because pickle deserialization can execute code.
            pickle.dump(model, handle, protocol=5)

        prediction_path = staging / ARTIFACT_NAMES[1]
        months = tuple(row.month for row in split.test)
        _write_predictions(
            prediction_path,
            months,
            actual,
            forecast.point,
            forecast.lower_p10,
            forecast.upper_p90,
        )
        chart_path = staging / ARTIFACT_NAMES[2]
        _write_chart(
            chart_path,
            months,
            actual,
            forecast.point,
            forecast.lower_p10,
            forecast.upper_p90,
        )

        metrics_path = staging / ARTIFACT_NAMES[3]
        _write_json(
            metrics_path,
            {
                "schema_version": ARTIFACT_VERSION,
                "evaluation_partition": {
                    "start": split.test[0].month.isoformat(),
                    "end": split.test[-1].month.isoformat(),
                    "rows": len(split.test),
                },
                "psi_subject": "predicted_revenue_eur",
                "psi_expected_distribution": "in_sample_training_predictions",
                "metrics": metrics,
            },
        )
        card_path = staging / ARTIFACT_NAMES[4]
        card_path.write_text(_model_card(metrics, len(training.targets)), encoding="utf-8")

        artifact_hashes = {
            path.name: _sha256(path)
            for path in (model_path, prediction_path, chart_path, metrics_path, card_path)
        }
        manifest_path = staging / ARTIFACT_NAMES[5]
        _write_json(
            manifest_path,
            {
                "schema_version": ARTIFACT_VERSION,
                "algorithm": "RandomForestRegressor",
                "artifact_hashes_sha256": artifact_hashes,
                "dataset": {
                    "path": str(dataset.resolve().relative_to(REPOSITORY_ROOT)),
                    "sha256": _sha256(dataset),
                    "generated": True,
                    "generator_seed": 42,
                },
                "estimator_parameters": ESTIMATOR_PARAMETERS,
                "feature_definitions": [
                    {
                        "name": definition.name,
                        "source": definition.source,
                        "lag_months": definition.lag_months,
                        "knowable_in_advance": definition.knowable_in_advance,
                    }
                    for definition in FEATURE_DEFINITIONS
                ],
                "feature_names": FEATURE_NAMES,
                "forecast_protocol": "strict_origin_time_recursive_per_tree",
                "prediction_band": {
                    "lower_percentile": 10,
                    "upper_percentile": 90,
                    "meaning": "ensemble_spread_not_calibrated_interval",
                },
                "random_seed": RANDOM_SEED,
                "scaling": "not_applied_tree_ensembles_are_scale_invariant",
                "split": {
                    "train_start": split.train[0].month.isoformat(),
                    "train_end": split.train[-1].month.isoformat(),
                    "train_source_rows": len(split.train),
                    "train_post_lag_rows": len(training.targets),
                    "test_start": split.test[0].month.isoformat(),
                    "test_end": split.test[-1].month.isoformat(),
                    "test_rows": len(split.test),
                },
                "versions": {
                    "python": platform.python_version(),
                    "matplotlib": version("matplotlib"),
                    "numpy": version("numpy"),
                    "scikit-learn": version("scikit-learn"),
                    "scipy": version("scipy"),
                },
            },
        )

        # The manifest is the completion marker and is installed last.
        for name in ARTIFACT_NAMES[:-1]:
            os.replace(staging / name, output_dir / name)
        os.replace(manifest_path, output_dir / manifest_path.name)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="also write the Phase 6.5.b chronological evaluation artifacts",
    )
    args = parser.parse_args()
    try:
        metrics = train(args.dataset, args.output_dir, force=args.force)
        evaluation = (
            evaluate(
                args.dataset,
                args.output_dir,
                metrics,
                force=args.force,
            )
            if args.evaluate
            else None
        )
    except (MetricError, OSError, SalesDataError, ValueError) as exc:
        print(f"sales forecast failed: {exc}")
        return 1
    print(
        json.dumps(
            {"holdout_metrics": metrics, "evaluation": evaluation},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
