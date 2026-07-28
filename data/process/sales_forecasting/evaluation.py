"""Chronological cross-validation and learning-curve evidence for Phase 6.5.b."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Final

import numpy as np
from sklearn.model_selection import TimeSeriesSplit

from .data import MonthlySales, SalesDataError
from .features import MAX_LAG, build_training_features
from .metrics import mean_absolute_error, mean_squared_error
from .modeling import fit_estimator, recursive_ensemble_forecast

DEFAULT_CV_SPLITS: Final = 5
STANDARD_DEVIATION_CONVENTION: Final = "population_ddof_0"


@dataclass(frozen=True)
class FoldEvaluation:
    fold: int
    train_indices: tuple[int, ...]
    validation_indices: tuple[int, ...]
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    train_source_rows: int
    train_post_lag_rows: int
    validation_rows: int
    train_mae_eur: float
    train_rmse_eur: float
    validation_mae_eur: float
    validation_rmse_eur: float

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for field in ("train_start", "train_end", "validation_start", "validation_end"):
            payload[field] = getattr(self, field).isoformat()
        payload["train_indices"] = list(self.train_indices)
        payload["validation_indices"] = list(self.validation_indices)
        return payload


@dataclass(frozen=True)
class MetricSummary:
    mean_eur: float
    standard_deviation_eur: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class CrossValidationEvaluation:
    folds: tuple[FoldEvaluation, ...]
    train_mae: MetricSummary
    train_rmse: MetricSummary
    validation_mae: MetricSummary
    validation_rmse: MetricSummary
    standard_deviation_convention: str = STANDARD_DEVIATION_CONVENTION

    def as_dict(self) -> dict[str, object]:
        return {
            "folds": [fold.as_dict() for fold in self.folds],
            "summary": {
                "train_mae_eur": self.train_mae.as_dict(),
                "train_rmse_eur": self.train_rmse.as_dict(),
                "validation_mae_eur": self.validation_mae.as_dict(),
                "validation_rmse_eur": self.validation_rmse.as_dict(),
            },
            "standard_deviation_convention": self.standard_deviation_convention,
        }


def _summary(values: tuple[float, ...]) -> MetricSummary:
    array = np.asarray(values, dtype=np.float64)
    return MetricSummary(
        mean_eur=float(np.mean(array)),
        standard_deviation_eur=float(np.std(array, ddof=0)),
    )


def chronological_fold_indices(
    row_count: int,
    *,
    n_splits: int = DEFAULT_CV_SPLITS,
) -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
    """Return expanding-window folds with non-overlapping chronological validation windows."""
    if n_splits < 5:
        raise SalesDataError("time-aware evaluation requires at least five folds")
    if row_count <= MAX_LAG + n_splits:
        raise SalesDataError("not enough chronological rows for cross-validation")
    splitter = TimeSeriesSplit(n_splits=n_splits)
    folds = tuple(
        (
            tuple(int(index) for index in train_indices),
            tuple(int(index) for index in validation_indices),
        )
        for train_indices, validation_indices in splitter.split(np.arange(row_count))
    )
    previous_validation_end = -1
    for train_indices, validation_indices in folds:
        if not train_indices or not validation_indices:
            raise SalesDataError("cross-validation folds must be non-empty")
        if tuple(sorted(train_indices)) != train_indices:
            raise SalesDataError("cross-validation training indices must be ordered")
        if tuple(sorted(validation_indices)) != validation_indices:
            raise SalesDataError("cross-validation validation indices must be ordered")
        if set(train_indices) & set(validation_indices):
            raise SalesDataError("cross-validation fold indices overlap")
        if max(train_indices) >= min(validation_indices):
            raise SalesDataError("every training index must precede validation")
        if min(validation_indices) <= previous_validation_end:
            raise SalesDataError("validation windows must advance without overlap")
        previous_validation_end = max(validation_indices)
    return folds


def evaluate_chronological_cv(
    training_rows: tuple[MonthlySales, ...],
    *,
    n_splits: int = DEFAULT_CV_SPLITS,
) -> CrossValidationEvaluation:
    """Evaluate expanding prefixes without using any future fold or holdout target."""
    folds: list[FoldEvaluation] = []
    for fold_number, (train_indices, validation_indices) in enumerate(
        chronological_fold_indices(len(training_rows), n_splits=n_splits),
        start=1,
    ):
        train_rows = tuple(training_rows[index] for index in train_indices)
        validation_rows = tuple(training_rows[index] for index in validation_indices)
        features = build_training_features(train_rows)
        model = fit_estimator(features)
        train_predictions = np.asarray(model.predict(features.values), dtype=np.float64)
        validation_forecast = recursive_ensemble_forecast(
            model,
            train_rows,
            validation_rows,
        )
        validation_actual = np.asarray(
            [row.revenue_eur for row in validation_rows],
            dtype=np.float64,
        )
        folds.append(
            FoldEvaluation(
                fold=fold_number,
                train_indices=train_indices,
                validation_indices=validation_indices,
                train_start=train_rows[0].month,
                train_end=train_rows[-1].month,
                validation_start=validation_rows[0].month,
                validation_end=validation_rows[-1].month,
                train_source_rows=len(train_rows),
                train_post_lag_rows=len(features.targets),
                validation_rows=len(validation_rows),
                train_mae_eur=mean_absolute_error(features.targets, train_predictions),
                train_rmse_eur=math.sqrt(
                    mean_squared_error(features.targets, train_predictions)
                ),
                validation_mae_eur=mean_absolute_error(
                    validation_actual,
                    validation_forecast.point,
                ),
                validation_rmse_eur=math.sqrt(
                    mean_squared_error(validation_actual, validation_forecast.point)
                ),
            )
        )
    fold_tuple = tuple(folds)
    return CrossValidationEvaluation(
        folds=fold_tuple,
        train_mae=_summary(tuple(fold.train_mae_eur for fold in fold_tuple)),
        train_rmse=_summary(tuple(fold.train_rmse_eur for fold in fold_tuple)),
        validation_mae=_summary(
            tuple(fold.validation_mae_eur for fold in fold_tuple)
        ),
        validation_rmse=_summary(
            tuple(fold.validation_rmse_eur for fold in fold_tuple)
        ),
    )
