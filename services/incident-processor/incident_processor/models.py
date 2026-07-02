"""Safe result models for incident analysis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .constants import CATEGORY_ORDER, COUNTRY_ORDER, RULES, SCORE_LABELS, SCORE_ORDER, STATUS_ORDER


def decimal_string(value: Decimal, places: str) -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def percentage_string(count: int, total: int) -> str:
    if total <= 0:
        return "0.0"
    return decimal_string((Decimal(count) * Decimal("100")) / Decimal(total), "0.1")


class IncidentCsvError(Exception):
    """A safe, non-data-leaking CSV error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class SafeValidationError:
    """A row-level validation error with no offending value or raw row."""

    row_number: int
    field: str
    code: str

    def to_dict(self) -> dict[str, int | str]:
        return {
            "row_number": self.row_number,
            "field": self.field,
            "code": self.code,
        }


@dataclass(frozen=True)
class AnalysisResult:
    """Aggregate analysis only; this model cannot carry customer emails."""

    total_records: int
    valid_records: int
    invalid_records: int
    invalid_rule_counts: dict[str, int]
    category_counts: dict[str, int]
    status_counts: dict[str, int]
    country_counts: dict[str, int]
    satisfaction_score_counts: dict[int, int]
    closed_incidents: int
    scored_incidents: int
    satisfaction_average: Decimal
    validation_errors: tuple[SafeValidationError, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "invalid_rules": [
                {
                    "code": rule.code,
                    "field": rule.field,
                    "label": rule.label,
                    "count": self.invalid_rule_counts.get(rule.code, 0),
                }
                for rule in RULES
            ],
            "categories": [
                {
                    "code": category,
                    "count": self.category_counts.get(category, 0),
                    "percentage": percentage_string(self.category_counts.get(category, 0), self.valid_records),
                }
                for category in CATEGORY_ORDER
            ],
            "statuses": [
                {
                    "code": status,
                    "count": self.status_counts.get(status, 0),
                    "percentage": percentage_string(self.status_counts.get(status, 0), self.valid_records),
                }
                for status in STATUS_ORDER
            ],
            "countries": [
                {
                    "code": country,
                    "count": self.country_counts.get(country, 0),
                    "percentage": percentage_string(self.country_counts.get(country, 0), self.valid_records),
                }
                for country in COUNTRY_ORDER
            ],
            "satisfaction": {
                "closed_incidents": self.closed_incidents,
                "scored_incidents": self.scored_incidents,
                "average_score": decimal_string(self.satisfaction_average, "0.01"),
                "scores": [
                    {
                        "score": score,
                        "label": SCORE_LABELS[score],
                        "count": self.satisfaction_score_counts.get(score, 0),
                    }
                    for score in SCORE_ORDER
                ],
            },
            "validation_errors": [error.to_dict() for error in self.validation_errors],
        }

