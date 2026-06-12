"""Shared incident processor constants."""

from __future__ import annotations

from dataclasses import dataclass

REQUIRED_FIELDS: tuple[str, ...] = (
    "incident_id",
    "date",
    "country",
    "customer_type",
    "tracking_number",
    "carrier",
    "category",
    "description",
    "status",
    "customer_email",
    "satisfaction_score",
)

CATEGORY_ORDER: tuple[str, ...] = (
    "LOST_PARCEL",
    "DELAYED_DELIVERY",
    "WRONG_ADDRESS",
    "RETURN_REQUEST",
    "DAMAGE",
)

STATUS_ORDER: tuple[str, ...] = ("OPEN", "CLOSED", "DISCARDED")
COUNTRY_ORDER: tuple[str, ...] = ("US", "ES")
CUSTOMER_TYPE_ORDER: tuple[str, ...] = ("B2B", "B2C")
SCORE_ORDER: tuple[int, ...] = (1, 2, 3, 4, 5)

SCORE_LABELS: dict[int, str] = {
    1: "Very dissatisfied",
    2: "Dissatisfied",
    3: "Neutral",
    4: "Satisfied",
    5: "Very satisfied",
}

VALID_CARRIERS_BY_COUNTRY: dict[str, tuple[str, ...]] = {
    "US": ("UPS", "FEDEX", "DHL_US"),
    "ES": ("MRW", "SEUR", "DHL_ES", "LOCAL_ES"),
}

ALL_CARRIERS = frozenset(
    carrier
    for carriers in VALID_CARRIERS_BY_COUNTRY.values()
    for carrier in carriers
)


@dataclass(frozen=True)
class RuleDefinition:
    code: str
    field: str
    label: str


RULES: tuple[RuleDefinition, ...] = (
    RuleDefinition("INVALID_INCIDENT_ID", "incident_id", "Invalid incident ID"),
    RuleDefinition("DUPLICATE_INCIDENT_ID", "incident_id", "Duplicate incident ID"),
    RuleDefinition("INVALID_DATE", "date", "Invalid date"),
    RuleDefinition("INVALID_COUNTRY", "country", "Invalid country"),
    RuleDefinition("INVALID_CUSTOMER_TYPE", "customer_type", "Invalid customer type"),
    RuleDefinition("INVALID_TRACKING_NUMBER", "tracking_number", "Invalid tracking number"),
    RuleDefinition("CARRIER_COUNTRY_MISMATCH", "carrier", "Carrier/country mismatch"),
    RuleDefinition("INVALID_CATEGORY", "category", "Invalid or missing category"),
    RuleDefinition("INVALID_DESCRIPTION", "description", "Invalid or missing description"),
    RuleDefinition("INVALID_STATUS", "status", "Invalid status"),
    RuleDefinition("INVALID_EMAIL", "customer_email", "Invalid or missing email"),
    RuleDefinition(
        "MISSING_SATISFACTION_SCORE",
        "satisfaction_score",
        "Closed incident, no score",
    ),
    RuleDefinition("INVALID_SATISFACTION_SCORE", "satisfaction_score", "Invalid satisfaction score"),
)

RULE_BY_CODE = {rule.code: rule for rule in RULES}

