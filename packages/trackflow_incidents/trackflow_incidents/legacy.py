"""Privacy-safe validation for the historical customer-service CSV."""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from io import StringIO

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

CATEGORY_ORDER = ("LOST_PARCEL", "DELAYED_DELIVERY", "WRONG_ADDRESS", "RETURN_REQUEST", "DAMAGE")
STATUS_ORDER = ("OPEN", "CLOSED", "DISCARDED")
COUNTRY_ORDER = ("US", "ES")
CUSTOMER_TYPE_ORDER = ("B2B", "B2C")
SCORE_ORDER = (1, 2, 3, 4, 5)
SCORE_LABELS = {
    1: "Very dissatisfied",
    2: "Dissatisfied",
    3: "Neutral",
    4: "Satisfied",
    5: "Very satisfied",
}
VALID_CARRIERS_BY_COUNTRY = {
    "US": ("UPS", "FEDEX", "DHL_US"),
    "ES": ("MRW", "SEUR", "DHL_ES", "LOCAL_ES"),
}
ALL_CARRIERS = frozenset(carrier for carriers in VALID_CARRIERS_BY_COUNTRY.values() for carrier in carriers)

INCIDENT_ID_PATTERN = re.compile(r"^TRF-\d{6}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCORE_PATTERN = re.compile(r"^[1-5]$")


@dataclass(frozen=True)
class RuleDefinition:
    code: str
    field: str
    label: str


RULES = (
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
    RuleDefinition("MISSING_SATISFACTION_SCORE", "satisfaction_score", "Closed incident, no score"),
    RuleDefinition("INVALID_SATISFACTION_SCORE", "satisfaction_score", "Invalid satisfaction score"),
)
RULE_BY_CODE = {rule.code: rule for rule in RULES}


class LegacyCsvError(Exception):
    """A CSV-level failure with no row values attached."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LegacyValidationError:
    row_number: int
    field: str
    code: str


@dataclass(frozen=True)
class LegacyIncidentRow:
    """Validated non-email fields needed by analysis and import."""

    row_number: int
    incident_id: str
    date: str
    country: str
    customer_type: str
    tracking_number: str
    carrier: str
    category: str
    description: str
    status: str
    satisfaction_score: str


@dataclass(frozen=True)
class LegacyValidationResult:
    total_records: int
    valid_rows: tuple[LegacyIncidentRow, ...]
    errors: tuple[LegacyValidationError, ...]

    @property
    def invalid_records(self) -> int:
        return len({error.row_number for error in self.errors})


@dataclass(frozen=True)
class _ParsedRow:
    row_number: int
    fields: dict[str, str]


def parse_legacy_csv(data: bytes) -> LegacyValidationResult:
    rows = _parse_rows(data)
    id_counts = Counter(
        row.fields["incident_id"] for row in rows if INCIDENT_ID_PATTERN.fullmatch(row.fields["incident_id"])
    )
    valid_rows: list[LegacyIncidentRow] = []
    errors: list[LegacyValidationError] = []
    for row in rows:
        row_errors = _validate_row(row, id_counts)
        if row_errors:
            errors.extend(row_errors)
            continue
        fields = row.fields
        valid_rows.append(
            LegacyIncidentRow(
                row_number=row.row_number,
                incident_id=fields["incident_id"],
                date=fields["date"],
                country=fields["country"],
                customer_type=fields["customer_type"],
                tracking_number=fields["tracking_number"],
                carrier=fields["carrier"],
                category=fields["category"],
                description=fields["description"],
                status=fields["status"],
                satisfaction_score=fields["satisfaction_score"],
            )
        )
    return LegacyValidationResult(len(rows), tuple(valid_rows), tuple(errors))


def _parse_rows(data: bytes) -> list[_ParsedRow]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LegacyCsvError("ENCODING_ERROR", "CSV file must be UTF-8 encoded.") from exc
    reader = csv.reader(StringIO(text), strict=True)
    try:
        raw_rows = [(reader.line_num, row) for row in reader]
    except csv.Error as exc:
        raise LegacyCsvError("MALFORMED_CSV", "CSV file could not be parsed.") from exc
    if not raw_rows:
        raise LegacyCsvError("MISSING_HEADERS", "CSV header row is required.")
    header = [value.strip() for value in raw_rows[0][1]]
    if any(field not in header for field in REQUIRED_FIELDS):
        raise LegacyCsvError("MISSING_HEADERS", "CSV is missing required headers.")
    body_rows = raw_rows[1:]
    while body_rows and (not body_rows[-1][1] or all(not value.strip() for value in body_rows[-1][1])):
        body_rows.pop()
    parsed: list[_ParsedRow] = []
    for row_number, row in body_rows:
        if len(row) > len(header):
            raise LegacyCsvError("MALFORMED_CSV", "CSV row has more values than headers.")
        fields = {
            field: (row[header.index(field)].strip() if header.index(field) < len(row) else "")
            for field in REQUIRED_FIELDS
        }
        parsed.append(_ParsedRow(row_number, fields))
    return parsed


def _validate_row(row: _ParsedRow, id_counts: Counter[str]) -> list[LegacyValidationError]:
    fields = row.fields
    errors: list[LegacyValidationError] = []

    def add(field: str, code: str) -> None:
        errors.append(LegacyValidationError(row.row_number, field, code))

    incident_id = fields["incident_id"]
    if not INCIDENT_ID_PATTERN.fullmatch(incident_id):
        add("incident_id", "INVALID_INCIDENT_ID")
    elif id_counts[incident_id] > 1:
        add("incident_id", "DUPLICATE_INCIDENT_ID")

    incident_date = fields["date"]
    if not DATE_PATTERN.fullmatch(incident_date):
        add("date", "INVALID_DATE")
    else:
        try:
            if date.fromisoformat(incident_date).isoformat() != incident_date:
                add("date", "INVALID_DATE")
        except ValueError:
            add("date", "INVALID_DATE")

    country = fields["country"]
    if country not in COUNTRY_ORDER:
        add("country", "INVALID_COUNTRY")
    if fields["customer_type"] not in CUSTOMER_TYPE_ORDER:
        add("customer_type", "INVALID_CUSTOMER_TYPE")
    if len(fields["tracking_number"]) < 8:
        add("tracking_number", "INVALID_TRACKING_NUMBER")

    carrier = fields["carrier"]
    if not carrier:
        add("carrier", "CARRIER_COUNTRY_MISMATCH")
    elif country in VALID_CARRIERS_BY_COUNTRY:
        if carrier not in VALID_CARRIERS_BY_COUNTRY[country]:
            add("carrier", "CARRIER_COUNTRY_MISMATCH")
    elif carrier not in ALL_CARRIERS:
        add("carrier", "CARRIER_COUNTRY_MISMATCH")

    if fields["category"] not in CATEGORY_ORDER:
        add("category", "INVALID_CATEGORY")
    if len(fields["description"]) < 5:
        add("description", "INVALID_DESCRIPTION")

    status = fields["status"]
    if status not in STATUS_ORDER:
        add("status", "INVALID_STATUS")
    email = fields["customer_email"]
    if not email or "@" not in email:
        add("customer_email", "INVALID_EMAIL")
    score = fields["satisfaction_score"]
    if status == "CLOSED" and not score:
        add("satisfaction_score", "MISSING_SATISFACTION_SCORE")
    elif score and not SCORE_PATTERN.fullmatch(score):
        add("satisfaction_score", "INVALID_SATISFACTION_SCORE")
    return errors

