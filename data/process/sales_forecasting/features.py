"""Predeclared causal features for strict origin-time forecasting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Final

import numpy as np
from numpy.typing import NDArray

from .data import MonthlySales, SalesDataError

MAX_LAG: Final = 12
BANNED_CONTEMPORANEOUS_SOURCES: Final = frozenset(
    {"revenue_eur", "shipments_processed", "avg_revenue_per_shipment_eur"}
)


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    source: str
    lag_months: int | None
    knowable_in_advance: bool


FEATURE_DEFINITIONS: Final = (
    FeatureDefinition("month_sin", "calendar_month", None, True),
    FeatureDefinition("month_cos", "calendar_month", None, True),
    FeatureDefinition("quarter", "calendar_month", None, True),
    FeatureDefinition("is_peak_month", "calendar_month", None, True),
    FeatureDefinition("is_february_trough", "calendar_month", None, True),
    FeatureDefinition("time_index", "calendar_sequence", None, True),
    FeatureDefinition("revenue_lag_1_eur", "revenue_eur", 1, True),
    FeatureDefinition("revenue_lag_12_eur", "revenue_eur", 12, True),
)
FEATURE_NAMES: Final = tuple(definition.name for definition in FEATURE_DEFINITIONS)


@dataclass(frozen=True)
class FeatureMatrix:
    values: NDArray[np.float64]
    targets: NDArray[np.float64]
    months: tuple[date, ...]
    names: tuple[str, ...] = FEATURE_NAMES


def assert_causal_feature_contract() -> None:
    """Fail if a declared feature can use a contemporaneous target/companion value."""
    for definition in FEATURE_DEFINITIONS:
        if not definition.knowable_in_advance:
            raise SalesDataError(f"feature {definition.name} is not knowable in advance")
        if definition.source in BANNED_CONTEMPORANEOUS_SOURCES:
            if definition.source != "revenue_eur" or definition.lag_months is None:
                raise SalesDataError(f"feature {definition.name} uses a contemporaneous companion")
            if definition.lag_months < 1:
                raise SalesDataError(f"feature {definition.name} leaks the same-month target")


def feature_values(month: date, time_index: int, revenue_history: list[float]) -> tuple[float, ...]:
    """Construct one feature vector using only calendar data and prior revenue."""
    assert_causal_feature_contract()
    if time_index != len(revenue_history):
        raise SalesDataError("feature time index must equal the available revenue-history length")
    if len(revenue_history) < MAX_LAG:
        raise SalesDataError("at least 12 prior revenue months are required")
    angle = 2.0 * math.pi * (month.month - 1) / 12.0
    return (
        math.sin(angle),
        math.cos(angle),
        float((month.month - 1) // 3 + 1),
        float(month.month in {11, 12}),
        float(month.month == 2),
        float(time_index),
        float(revenue_history[-1]),
        float(revenue_history[-12]),
    )


def build_training_features(rows: tuple[MonthlySales, ...]) -> FeatureMatrix:
    """Build training rows after the fixed 12-month lag warm-up."""
    if len(rows) <= MAX_LAG:
        raise SalesDataError("training requires more than 12 chronological months")
    if any(left.month >= right.month for left, right in pairwise(rows)):
        raise SalesDataError("training rows must be strictly chronological")
    history = [row.revenue_eur for row in rows[:MAX_LAG]]
    matrix: list[tuple[float, ...]] = []
    targets: list[float] = []
    months: list[date] = []
    for index in range(MAX_LAG, len(rows)):
        row = rows[index]
        matrix.append(feature_values(row.month, index, history))
        targets.append(row.revenue_eur)
        months.append(row.month)
        history.append(row.revenue_eur)
    return FeatureMatrix(
        values=np.asarray(matrix, dtype=np.float64),
        targets=np.asarray(targets, dtype=np.float64),
        months=tuple(months),
    )
