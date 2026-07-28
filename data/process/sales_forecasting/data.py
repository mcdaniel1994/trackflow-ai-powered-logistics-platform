"""Strict parsing and temporal partitioning for the fixed sales dataset."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

EXPECTED_COLUMNS = (
    "month",
    "revenue_eur",
    "shipments_processed",
    "avg_revenue_per_shipment_eur",
    "market",
)
TRAIN_START = date(2016, 1, 1)
TRAIN_END = date(2023, 12, 1)
TEST_START = date(2024, 1, 1)
TEST_END = date(2025, 12, 1)


class SalesDataError(ValueError):
    """Raised when sales input cannot support a trustworthy forecast."""


@dataclass(frozen=True)
class MonthlySales:
    month: date
    revenue_eur: float
    shipments_processed: int
    avg_revenue_per_shipment_eur: float
    market: str


@dataclass(frozen=True)
class TemporalSplit:
    train: tuple[MonthlySales, ...]
    test: tuple[MonthlySales, ...]


def _parse_month(raw: str, line_number: int) -> date:
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SalesDataError(f"line {line_number}: month must use YYYY-MM-01") from exc
    if parsed.day != 1 or parsed.isoformat() != raw:
        raise SalesDataError(f"line {line_number}: month must use YYYY-MM-01")
    return parsed


def _parse_positive_float(raw: str, field: str, line_number: int) -> float:
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise SalesDataError(f"line {line_number}: {field} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise SalesDataError(f"line {line_number}: {field} must be positive and finite")
    return parsed


def _parse_positive_int(raw: str, field: str, line_number: int) -> int:
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise SalesDataError(f"line {line_number}: {field} must be an integer") from exc
    if str(parsed) != raw or parsed <= 0:
        raise SalesDataError(f"line {line_number}: {field} must be a positive integer")
    return parsed


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _expected_months() -> tuple[date, ...]:
    months: list[date] = []
    current = TRAIN_START
    while current <= TEST_END:
        months.append(current)
        current = _next_month(current)
    return tuple(months)


def validate_sales_rows(rows: tuple[MonthlySales, ...]) -> tuple[MonthlySales, ...]:
    """Validate the exact complete series and return it unchanged."""
    expected_months = _expected_months()
    if len(rows) != len(expected_months):
        raise SalesDataError(f"expected 120 monthly rows, found {len(rows)}")
    if tuple(row.month for row in rows) != expected_months:
        raise SalesDataError("months must be a unique, ordered, gap-free 2016-01 through 2025-12 series")
    if any(row.market != "consolidated" for row in rows):
        raise SalesDataError("every row must use market='consolidated'")
    for row in rows:
        implied_average = round(row.revenue_eur / row.shipments_processed, 2)
        if abs(implied_average - row.avg_revenue_per_shipment_eur) > 0.005:
            raise SalesDataError(
                f"{row.month.isoformat()}: average revenue per shipment is internally inconsistent"
            )
    return rows


def load_sales_csv(source: Path) -> tuple[MonthlySales, ...]:
    """Load and validate the fixed TrackFlow CSV without silent imputation."""
    try:
        with source.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(EXPECTED_COLUMNS):
                raise SalesDataError(
                    f"expected columns {list(EXPECTED_COLUMNS)}, found {reader.fieldnames}"
                )
            rows: list[MonthlySales] = []
            for line_number, record in enumerate(reader, start=2):
                if any(record[field] is None or not record[field].strip() for field in EXPECTED_COLUMNS):
                    raise SalesDataError(f"line {line_number}: null or empty values are not allowed")
                rows.append(
                    MonthlySales(
                        month=_parse_month(record["month"], line_number),
                        revenue_eur=_parse_positive_float(
                            record["revenue_eur"], "revenue_eur", line_number
                        ),
                        shipments_processed=_parse_positive_int(
                            record["shipments_processed"], "shipments_processed", line_number
                        ),
                        avg_revenue_per_shipment_eur=_parse_positive_float(
                            record["avg_revenue_per_shipment_eur"],
                            "avg_revenue_per_shipment_eur",
                            line_number,
                        ),
                        market=record["market"],
                    )
                )
    except OSError as exc:
        raise SalesDataError(f"cannot read sales dataset: {exc}") from exc
    return validate_sales_rows(tuple(rows))


def temporal_split(rows: tuple[MonthlySales, ...]) -> TemporalSplit:
    """Split by fixed calendar boundaries; no row can occur in both partitions."""
    validated = validate_sales_rows(rows)
    train = tuple(row for row in validated if TRAIN_START <= row.month <= TRAIN_END)
    test = tuple(row for row in validated if TEST_START <= row.month <= TEST_END)
    if len(train) != 96 or len(test) != 24:
        raise SalesDataError("the temporal split must contain 96 train and 24 test months")
    if set(train) & set(test):
        raise SalesDataError("training and test rows overlap")
    if train[-1].month >= test[0].month:
        raise SalesDataError("training must end before testing begins")
    return TemporalSplit(train=train, test=test)
