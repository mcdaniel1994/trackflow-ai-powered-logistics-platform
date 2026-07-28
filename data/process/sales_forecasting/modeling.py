"""Fixed Random Forest training and strict recursive ensemble forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import RandomForestRegressor

from .data import MonthlySales, SalesDataError
from .features import FeatureMatrix, feature_values

RANDOM_SEED: Final = 42
ESTIMATOR_PARAMETERS: Final[dict[str, int | float | bool | None]] = {
    "n_estimators": 400,
    "max_depth": 6,
    "min_samples_leaf": 2,
    "max_features": 0.75,
    "bootstrap": True,
    "random_state": RANDOM_SEED,
    "n_jobs": 1,
}


@dataclass(frozen=True)
class Forecast:
    point: NDArray[np.float64]
    lower_p10: NDArray[np.float64]
    upper_p90: NDArray[np.float64]
    per_tree: NDArray[np.float64]


def new_estimator() -> RandomForestRegressor:
    """Return the predeclared, untuned estimator used for the accepted baseline."""
    # Random Forest is selected for n=84 post-lag training rows: bagging is
    # robust at this scale, independent trees are explainable to Finance, and
    # their spread supplies an honest variability band without a tuning budget.
    return RandomForestRegressor(**ESTIMATOR_PARAMETERS)


def fit_estimator(features: FeatureMatrix) -> RandomForestRegressor:
    model = new_estimator()
    model.fit(features.values, features.targets)
    return model


def recursive_ensemble_forecast(
    model: RandomForestRegressor,
    train_rows: tuple[MonthlySales, ...],
    test_rows: tuple[MonthlySales, ...],
) -> Forecast:
    """Forecast from the 2023-12 origin without using any observed test target."""
    estimators = getattr(model, "estimators_", None)
    if not estimators:
        raise SalesDataError("the Random Forest must be fitted before forecasting")
    if not train_rows or not test_rows or train_rows[-1].month >= test_rows[0].month:
        raise SalesDataError("forecast partitions must be non-empty and chronological")

    paths: list[list[float]] = []
    for tree in estimators:
        history = [row.revenue_eur for row in train_rows]
        path: list[float] = []
        for row in test_rows:
            vector = np.asarray(
                [feature_values(row.month, len(history), history)], dtype=np.float64
            )
            prediction = float(tree.predict(vector)[0])
            path.append(prediction)
            history.append(prediction)
        paths.append(path)

    per_tree = np.asarray(paths, dtype=np.float64)
    return Forecast(
        point=np.mean(per_tree, axis=0),
        lower_p10=np.percentile(per_tree, 10, axis=0),
        upper_p90=np.percentile(per_tree, 90, axis=0),
        per_tree=per_tree,
    )
