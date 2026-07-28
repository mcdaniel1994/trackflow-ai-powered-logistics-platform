"""Binding regression metrics for Engagement 6.5.a."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import normaltest


class MetricError(ValueError):
    """Raised when a metric receives an invalid or unsupported sample."""


@dataclass(frozen=True)
class TestMetrics:
    mse_eur_squared: float
    rmse_eur: float
    rmse_percent_mean_test_revenue: float
    psi_predicted_revenue: float
    somers_d_gini: float
    k2_statistic: float
    k2_p_value: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


def _one_dimensional(values: ArrayLike, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise MetricError(f"{name} must be a non-empty one-dimensional sample")
    if not np.all(np.isfinite(array)):
        raise MetricError(f"{name} must contain only finite values")
    return array


def mean_squared_error(actual: ArrayLike, predicted: ArrayLike) -> float:
    actual_array = _one_dimensional(actual, "actual")
    predicted_array = _one_dimensional(predicted, "predicted")
    if actual_array.shape != predicted_array.shape:
        raise MetricError("actual and predicted must have identical shapes")
    return float(np.mean(np.square(actual_array - predicted_array)))


def mean_absolute_error(actual: ArrayLike, predicted: ArrayLike) -> float:
    """Return MAE in the target's business unit."""
    actual_array = _one_dimensional(actual, "actual")
    predicted_array = _one_dimensional(predicted, "predicted")
    if actual_array.shape != predicted_array.shape:
        raise MetricError("actual and predicted must have identical shapes")
    return float(np.mean(np.abs(actual_array - predicted_array)))


def population_stability_index(
    expected: ArrayLike,
    actual: ArrayLike,
    *,
    bins: int = 10,
    epsilon: float = 1e-6,
) -> float:
    """Compare predicted-revenue distributions using training-derived quantiles."""
    expected_array = _one_dimensional(expected, "expected")
    actual_array = _one_dimensional(actual, "actual")
    if bins < 2:
        raise MetricError("PSI requires at least two bins")
    if not 0 < epsilon < 1:
        raise MetricError("PSI epsilon must be between zero and one")

    quantiles = np.asarray(
        np.quantile(expected_array, np.linspace(0.0, 1.0, bins + 1)),
        dtype=np.float64,
    )
    interior_edges = quantiles[1:-1]
    expected_counts = np.bincount(
        np.searchsorted(interior_edges, expected_array, side="right"), minlength=bins
    )
    actual_counts = np.bincount(
        np.searchsorted(interior_edges, actual_array, side="right"), minlength=bins
    )
    expected_proportions = expected_counts.astype(np.float64) / expected_array.size
    actual_proportions = actual_counts.astype(np.float64) / actual_array.size
    expected_safe = np.maximum(expected_proportions, epsilon)
    actual_safe = np.maximum(actual_proportions, epsilon)
    expected_safe /= expected_safe.sum()
    actual_safe /= actual_safe.sum()
    return float(
        np.sum((actual_safe - expected_safe) * np.log(actual_safe / expected_safe))
    )


def somers_d(actual: ArrayLike, predicted: ArrayLike) -> float:
    """Continuous-target Gini: (concordant - discordant) / actual-comparable pairs."""
    actual_array = _one_dimensional(actual, "actual")
    predicted_array = _one_dimensional(predicted, "predicted")
    if actual_array.shape != predicted_array.shape:
        raise MetricError("actual and predicted must have identical shapes")

    concordant = 0
    discordant = 0
    comparable = 0
    for left in range(actual_array.size - 1):
        for right in range(left + 1, actual_array.size):
            actual_difference = actual_array[left] - actual_array[right]
            if actual_difference == 0:
                continue
            comparable += 1
            predicted_difference = predicted_array[left] - predicted_array[right]
            product = actual_difference * predicted_difference
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
    if comparable == 0:
        raise MetricError("Somers' D requires at least one pair with distinct actual values")
    return (concordant - discordant) / comparable


def k2_normality(residuals: ArrayLike) -> tuple[float, float]:
    residual_array = _one_dimensional(residuals, "residuals")
    if residual_array.size < 8:
        raise MetricError("D'Agostino-Pearson K2 requires at least 8 residuals")
    result = normaltest(residual_array)
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if not math.isfinite(statistic) or not math.isfinite(p_value):
        raise MetricError("D'Agostino-Pearson K2 produced a non-finite result")
    return statistic, p_value


def evaluate_test_metrics(
    actual: ArrayLike,
    predicted: ArrayLike,
    *,
    training_predictions: ArrayLike,
) -> TestMetrics:
    """Compute all binding metrics on test values, using train predictions only as PSI baseline."""
    actual_array = _one_dimensional(actual, "actual")
    predicted_array = _one_dimensional(predicted, "predicted")
    if actual_array.shape != predicted_array.shape:
        raise MetricError("actual and predicted must have identical shapes")
    mse = mean_squared_error(actual_array, predicted_array)
    rmse = math.sqrt(mse)
    k2_statistic, k2_p_value = k2_normality(actual_array - predicted_array)
    return TestMetrics(
        mse_eur_squared=mse,
        rmse_eur=rmse,
        rmse_percent_mean_test_revenue=rmse / float(np.mean(actual_array)) * 100.0,
        psi_predicted_revenue=population_stability_index(
            training_predictions, predicted_array
        ),
        somers_d_gini=somers_d(actual_array, predicted_array),
        k2_statistic=k2_statistic,
        k2_p_value=k2_p_value,
    )
