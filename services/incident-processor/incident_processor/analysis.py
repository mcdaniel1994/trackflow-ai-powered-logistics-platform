"""Aggregate analysis backed by the shared privacy-safe CSV validator."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

from trackflow_incidents import LegacyCsvError, parse_legacy_csv

from .constants import CATEGORY_ORDER, COUNTRY_ORDER, RULE_BY_CODE, SCORE_ORDER, STATUS_ORDER
from .models import AnalysisResult, IncidentCsvError, SafeValidationError


def analyze_csv_file(path: str | Path) -> AnalysisResult:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise IncidentCsvError("FILE_READ_ERROR", "CSV file could not be read.") from exc
    return analyze_csv_bytes(data)


def analyze_csv_bytes(data: bytes) -> AnalysisResult:
    try:
        validation = parse_legacy_csv(data)
    except LegacyCsvError as exc:
        raise IncidentCsvError(exc.code, exc.message) from exc

    invalid_rule_counts = Counter(error.code for error in validation.errors)
    category_counts = Counter(row.category for row in validation.valid_rows)
    status_counts = Counter(row.status for row in validation.valid_rows)
    country_counts = Counter(row.country for row in validation.valid_rows)
    closed_rows = [row for row in validation.valid_rows if row.status == "CLOSED"]
    scored_rows = [row for row in closed_rows if row.satisfaction_score]
    satisfaction_score_counts = Counter(int(row.satisfaction_score) for row in scored_rows)
    satisfaction_total = sum((Decimal(row.satisfaction_score) for row in scored_rows), Decimal("0"))
    satisfaction_average = satisfaction_total / Decimal(len(scored_rows)) if scored_rows else Decimal("0")

    return AnalysisResult(
        total_records=validation.total_records,
        valid_records=len(validation.valid_rows),
        invalid_records=validation.invalid_records,
        invalid_rule_counts={code: invalid_rule_counts.get(code, 0) for code in RULE_BY_CODE},
        category_counts={category: category_counts.get(category, 0) for category in CATEGORY_ORDER},
        status_counts={status: status_counts.get(status, 0) for status in STATUS_ORDER},
        country_counts={country: country_counts.get(country, 0) for country in COUNTRY_ORDER},
        satisfaction_score_counts={score: satisfaction_score_counts.get(score, 0) for score in SCORE_ORDER},
        closed_incidents=len(closed_rows),
        scored_incidents=len(scored_rows),
        satisfaction_average=satisfaction_average,
        validation_errors=tuple(
            SafeValidationError(error.row_number, error.field, error.code) for error in validation.errors
        ),
    )

