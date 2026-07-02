"""Shared TrackFlow incident contracts and legacy import helpers."""

from .contracts import (
    BRANCH_VALUES,
    CATEGORY_VALUES,
    ORIGIN_VALUES,
    STATUS_VALUES,
    Branch,
    IncidentCategory,
    IncidentOrigin,
    IncidentStatus,
)
from .legacy import (
    CATEGORY_ORDER,
    COUNTRY_ORDER,
    CUSTOMER_TYPE_ORDER,
    REQUIRED_FIELDS,
    RULE_BY_CODE,
    RULES,
    SCORE_LABELS,
    SCORE_ORDER,
    STATUS_ORDER,
    LegacyCsvError,
    LegacyIncidentRow,
    LegacyValidationError,
    LegacyValidationResult,
    parse_legacy_csv,
)
from .normalization import NormalizedIncident, normalize_legacy_incident

__all__ = [
    "BRANCH_VALUES",
    "CATEGORY_ORDER",
    "CATEGORY_VALUES",
    "COUNTRY_ORDER",
    "CUSTOMER_TYPE_ORDER",
    "ORIGIN_VALUES",
    "REQUIRED_FIELDS",
    "RULES",
    "RULE_BY_CODE",
    "SCORE_LABELS",
    "SCORE_ORDER",
    "STATUS_ORDER",
    "STATUS_VALUES",
    "Branch",
    "IncidentCategory",
    "IncidentOrigin",
    "IncidentStatus",
    "LegacyCsvError",
    "LegacyIncidentRow",
    "LegacyValidationError",
    "LegacyValidationResult",
    "NormalizedIncident",
    "normalize_legacy_incident",
    "parse_legacy_csv",
]

