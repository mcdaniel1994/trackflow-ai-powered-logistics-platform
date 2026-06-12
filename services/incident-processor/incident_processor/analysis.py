"""CSV parsing, validation, and aggregate analysis for TrackFlow incidents."""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from .constants import (
    ALL_CARRIERS,
    CATEGORY_ORDER,
    COUNTRY_ORDER,
    CUSTOMER_TYPE_ORDER,
    REQUIRED_FIELDS,
    RULE_BY_CODE,
    SCORE_ORDER,
    STATUS_ORDER,
    VALID_CARRIERS_BY_COUNTRY,
)
from .models import AnalysisResult, IncidentCsvError, SafeValidationError

INCIDENT_ID_PATTERN = re.compile(r"^TRF-\d{6}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCORE_PATTERN = re.compile(r"^[1-5]$")


@dataclass(frozen=True)
class ParsedRow:
    row_number: int
    fields: dict[str, str]


def analyze_csv_file(path: str | Path) -> AnalysisResult:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise IncidentCsvError("FILE_READ_ERROR", "CSV file could not be read.") from exc
    return analyze_csv_bytes(data)


def analyze_csv_bytes(data: bytes) -> AnalysisResult:
    rows = _parse_csv(data)
    return _analyze_rows(rows)


def _parse_csv(data: bytes) -> list[ParsedRow]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IncidentCsvError("ENCODING_ERROR", "CSV file must be UTF-8 encoded.") from exc

    reader = csv.reader(StringIO(text), strict=True)
    try:
        raw_rows = [(reader.line_num, row) for row in reader]
    except csv.Error as exc:
        raise IncidentCsvError("MALFORMED_CSV", "CSV file could not be parsed.") from exc

    if not raw_rows:
        raise IncidentCsvError("MISSING_HEADERS", "CSV header row is required.")

    _header_line, header = raw_rows[0]
    trimmed_header = [value.strip() for value in header]
    missing_headers = [field for field in REQUIRED_FIELDS if field not in trimmed_header]
    if missing_headers:
        raise IncidentCsvError("MISSING_HEADERS", "CSV is missing required headers.")

    body_rows = raw_rows[1:]
    # Spec: only trailing empty lines are file-formatting noise. A blank row
    # *inside* the data is kept and counted as an invalid record.
    while body_rows and _is_empty_csv_row(body_rows[-1][1]):
        body_rows.pop()

    parsed: list[ParsedRow] = []
    for row_number, row in body_rows:
        if len(row) > len(trimmed_header):
            raise IncidentCsvError("MALFORMED_CSV", "CSV row has more values than headers.")
        fields = {
            field: (row[trimmed_header.index(field)].strip() if trimmed_header.index(field) < len(row) else "")
            for field in REQUIRED_FIELDS
        }
        parsed.append(ParsedRow(row_number=row_number, fields=fields))

    return parsed


def _is_empty_csv_row(row: list[str]) -> bool:
    return not row or all(value.strip() == "" for value in row)


def _analyze_rows(rows: list[ParsedRow]) -> AnalysisResult:
    id_counts = Counter(
        row.fields["incident_id"]
        for row in rows
        if INCIDENT_ID_PATTERN.fullmatch(row.fields["incident_id"])
    )

    invalid_rule_counts = {code: 0 for code in RULE_BY_CODE}
    category_counts = {category: 0 for category in CATEGORY_ORDER}
    status_counts = {status: 0 for status in STATUS_ORDER}
    country_counts = {country: 0 for country in COUNTRY_ORDER}
    satisfaction_score_counts = {score: 0 for score in SCORE_ORDER}

    invalid_rows = 0
    closed_incidents = 0
    scored_incidents = 0
    satisfaction_total = Decimal("0")
    validation_errors: list[SafeValidationError] = []

    for row in rows:
        errors = _validate_row(row, id_counts)
        if errors:
            # A row counts once toward invalid_records no matter how many rules
            # it breaks, but every triggered rule still bumps its own counter —
            # so the rule counters can sum to more than invalid_records.
            invalid_rows += 1
            validation_errors.extend(errors)
            for error in errors:
                invalid_rule_counts[error.code] += 1
            continue

        fields = row.fields
        category_counts[fields["category"]] += 1
        status_counts[fields["status"]] += 1
        country_counts[fields["country"]] += 1

        if fields["status"] == "CLOSED":
            closed_incidents += 1
            score = int(fields["satisfaction_score"])
            satisfaction_score_counts[score] += 1
            satisfaction_total += Decimal(score)
            scored_incidents += 1

    satisfaction_average = (
        satisfaction_total / Decimal(scored_incidents)
        if scored_incidents
        else Decimal("0")
    )

    return AnalysisResult(
        total_records=len(rows),
        valid_records=len(rows) - invalid_rows,
        invalid_records=invalid_rows,
        invalid_rule_counts=invalid_rule_counts,
        category_counts=category_counts,
        status_counts=status_counts,
        country_counts=country_counts,
        satisfaction_score_counts=satisfaction_score_counts,
        closed_incidents=closed_incidents,
        scored_incidents=scored_incidents,
        satisfaction_average=satisfaction_average,
        validation_errors=tuple(validation_errors),
    )


def _validate_row(row: ParsedRow, id_counts: Counter[str]) -> list[SafeValidationError]:
    fields = row.fields
    errors: list[SafeValidationError] = []

    def add(field: str, code: str) -> None:
        errors.append(SafeValidationError(row_number=row.row_number, field=field, code=code))

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

    # Privacy: the email value is read for this check and then dropped. It must
    # never be stored on a result, logged, or echoed in an error message.
    email = fields["customer_email"]
    if not email or "@" not in email:
        add("customer_email", "INVALID_EMAIL")

    score_value = fields["satisfaction_score"]
    if status == "CLOSED" and not score_value:
        add("satisfaction_score", "MISSING_SATISFACTION_SCORE")
    elif score_value and not SCORE_PATTERN.fullmatch(score_value):
        add("satisfaction_score", "INVALID_SATISFACTION_SCORE")

    return errors

