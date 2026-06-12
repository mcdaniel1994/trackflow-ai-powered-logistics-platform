from __future__ import annotations

from pathlib import Path

import pytest

from incident_processor.analysis import analyze_csv_bytes
from incident_processor.models import IncidentCsvError
from incident_processor.reporting import build_export_csv, format_console_report

FIXTURE = Path(__file__).parent / "fixtures" / "sample-incidents.csv"

HEADER = (
    "incident_id,date,country,customer_type,tracking_number,carrier,category,"
    "description,status,customer_email,satisfaction_score"
)


def make_row(**overrides: str) -> dict[str, str]:
    row = {
        "incident_id": "TRF-900001",
        "date": "2026-05-01",
        "country": "US",
        "customer_type": "B2B",
        "tracking_number": "USTRACK900001",
        "carrier": "UPS",
        "category": "LOST_PARCEL",
        "description": "Valid incident description",
        "status": "OPEN",
        "customer_email": "safe@example.com",
        "satisfaction_score": "",
    }
    row.update(overrides)
    return row


def csv_bytes(*rows: dict[str, str] | str) -> bytes:
    lines = [HEADER]
    for row in rows:
        if isinstance(row, str):
            lines.append(row)
            continue
        lines.append(",".join(row[field] for field in HEADER.split(",")))
    return ("\n".join(lines) + "\n").encode("utf-8")


def rule_counts(result):
    return {rule["code"]: rule["count"] for rule in result.to_dict()["invalid_rules"]}


def by_code(items):
    return {item["code"]: item for item in items}


def test_fixture_matches_trackflow_expected_metrics():
    result = analyze_csv_bytes(FIXTURE.read_bytes())
    data = result.to_dict()

    assert data["total_records"] == 100
    assert data["valid_records"] == 95
    assert data["invalid_records"] == 5

    assert {item["code"]: item["count"] for item in data["categories"]} == {
        "LOST_PARCEL": 14,
        "DELAYED_DELIVERY": 38,
        "WRONG_ADDRESS": 19,
        "RETURN_REQUEST": 17,
        "DAMAGE": 7,
    }
    assert {item["code"]: item["count"] for item in data["statuses"]} == {
        "OPEN": 29,
        "CLOSED": 52,
        "DISCARDED": 14,
    }
    assert {item["code"]: item["count"] for item in data["countries"]} == {"US": 50, "ES": 45}
    assert data["satisfaction"]["average_score"] == "3.06"
    assert {item["score"]: item["count"] for item in data["satisfaction"]["scores"]} == {
        1: 6,
        2: 11,
        3: 15,
        4: 14,
        5: 6,
    }

    counts = rule_counts(result)
    assert counts["INVALID_TRACKING_NUMBER"] == 1
    assert counts["CARRIER_COUNTRY_MISMATCH"] == 1
    assert counts["INVALID_CATEGORY"] == 1
    assert counts["INVALID_EMAIL"] == 1
    assert counts["MISSING_SATISFACTION_SCORE"] == 1


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("incident_id", "TRF-12345", "INVALID_INCIDENT_ID"),
        ("date", "2026-02-30", "INVALID_DATE"),
        ("date", "2026-5-01", "INVALID_DATE"),
        ("country", "us", "INVALID_COUNTRY"),
        ("customer_type", "b2b", "INVALID_CUSTOMER_TYPE"),
        ("tracking_number", "SHORT", "INVALID_TRACKING_NUMBER"),
        ("carrier", "MRW", "CARRIER_COUNTRY_MISMATCH"),
        ("category", "lost_parcel", "INVALID_CATEGORY"),
        ("description", "bad", "INVALID_DESCRIPTION"),
        ("status", "closed", "INVALID_STATUS"),
        ("customer_email", "safe.example.com", "INVALID_EMAIL"),
        ("satisfaction_score", "6", "INVALID_SATISFACTION_SCORE"),
        ("satisfaction_score", "abc", "INVALID_SATISFACTION_SCORE"),
    ],
)
def test_each_field_validation_rule(field: str, value: str, code: str):
    row = make_row(**{field: value})
    if field == "satisfaction_score":
        row["status"] = "CLOSED"
    result = analyze_csv_bytes(csv_bytes(row))

    assert result.invalid_records == 1
    assert rule_counts(result)[code] == 1


def test_missing_score_for_closed_incident_is_invalid():
    result = analyze_csv_bytes(csv_bytes(make_row(status="CLOSED", satisfaction_score="")))

    assert result.invalid_records == 1
    assert rule_counts(result)["MISSING_SATISFACTION_SCORE"] == 1


def test_duplicate_incident_ids_mark_all_duplicate_rows_invalid():
    row_a = make_row(incident_id="TRF-111111", tracking_number="USTRACK111111")
    row_b = make_row(incident_id="TRF-111111", tracking_number="USTRACK222222")
    result = analyze_csv_bytes(csv_bytes(row_a, row_b))

    assert result.invalid_records == 2
    assert rule_counts(result)["DUPLICATE_INCIDENT_ID"] == 2


def test_multiple_violations_increment_rules_but_count_one_invalid_row():
    result = analyze_csv_bytes(
        csv_bytes(
            make_row(
                country="ES",
                customer_type="b2b",
                tracking_number="BAD",
                carrier="UPS",
                category="NOPE",
                customer_email="not-an-email",
            )
        )
    )
    counts = rule_counts(result)

    assert result.invalid_records == 1
    assert counts["INVALID_CUSTOMER_TYPE"] == 1
    assert counts["INVALID_TRACKING_NUMBER"] == 1
    assert counts["CARRIER_COUNTRY_MISMATCH"] == 1
    assert counts["INVALID_CATEGORY"] == 1
    assert counts["INVALID_EMAIL"] == 1


def test_invalid_rows_are_excluded_from_metrics():
    valid = make_row(status="CLOSED", satisfaction_score="5")
    invalid = make_row(
        incident_id="TRF-900002",
        category="DAMAGE",
        status="CLOSED",
        satisfaction_score="",
    )
    result = analyze_csv_bytes(csv_bytes(valid, invalid))
    data = result.to_dict()

    assert result.valid_records == 1
    assert by_code(data["categories"])["DAMAGE"]["count"] == 0
    assert data["satisfaction"]["closed_incidents"] == 1
    assert data["satisfaction"]["average_score"] == "5.00"


def test_trailing_empty_lines_are_ignored_but_blank_records_inside_are_invalid():
    payload = (
        HEADER
        + "\n"
        + ",".join(make_row().values())
        + "\n\n"
        + ",".join(make_row(incident_id="TRF-900002", tracking_number="USTRACK900002").values())
        + "\n\n"
    ).encode("utf-8")
    result = analyze_csv_bytes(payload)

    assert result.total_records == 3
    assert result.valid_records == 2
    assert result.invalid_records == 1
    assert rule_counts(result)["INVALID_INCIDENT_ID"] == 1


def test_missing_headers_malformed_csv_and_encoding_errors_are_safe():
    with pytest.raises(IncidentCsvError, match="CSV is missing required headers"):
        analyze_csv_bytes(b"incident_id,date\nTRF-000001,2026-05-01\n")

    with pytest.raises(IncidentCsvError) as malformed:
        analyze_csv_bytes((HEADER + '\n"unterminated\n').encode("utf-8"))
    assert malformed.value.code == "MALFORMED_CSV"

    with pytest.raises(IncidentCsvError) as encoding:
        analyze_csv_bytes(b"\xff\xfe\x00")
    assert encoding.value.code == "ENCODING_ERROR"


def test_decimal_average_uses_round_half_up():
    rows = [
        make_row(incident_id="TRF-910001", tracking_number="USTRACK910001", status="CLOSED", satisfaction_score="1"),
        make_row(incident_id="TRF-910002", tracking_number="USTRACK910002", status="CLOSED", satisfaction_score="2"),
        make_row(incident_id="TRF-910003", tracking_number="USTRACK910003", status="CLOSED", satisfaction_score="2"),
    ]
    result = analyze_csv_bytes(csv_bytes(*rows))

    assert result.to_dict()["satisfaction"]["average_score"] == "1.67"


def test_export_rows_are_deterministic_and_ordered():
    result = analyze_csv_bytes(FIXTURE.read_bytes())
    export = build_export_csv(result)
    lines = export.splitlines()

    assert lines[0] == "section,metric,value,percentage"
    assert lines[1:4] == [
        "summary,total_records,100,",
        "summary,valid_records,95,",
        "summary,invalid_records,5,",
    ]
    assert "category,LOST_PARCEL,14,14.7" in lines
    assert "satisfaction,average_score,3.06," in lines
    assert export == build_export_csv(result)


def test_result_report_and_export_do_not_leak_emails():
    result = analyze_csv_bytes(FIXTURE.read_bytes())
    combined = (
        str(result.to_dict())
        + format_console_report(result, "sample-incidents.csv")
        + build_export_csv(result)
    )

    assert "@example.com" not in combined
    assert "customer1" not in combined



def test_file_read_error_is_safe(tmp_path):
    from incident_processor.analysis import analyze_csv_file

    with pytest.raises(IncidentCsvError) as excinfo:
        analyze_csv_file(tmp_path / "does-not-exist.csv")

    assert excinfo.value.code == "FILE_READ_ERROR"
    assert "does-not-exist" not in excinfo.value.message


def test_zero_closed_incidents_yield_zero_satisfaction_metrics():
    result = analyze_csv_bytes(
        csv_bytes(
            make_row(incident_id="TRF-900001", status="OPEN"),
            make_row(incident_id="TRF-900002", tracking_number="USTRACK900002", status="DISCARDED"),
        )
    )

    assert result.closed_incidents == 0
    assert result.scored_incidents == 0
    # Average must be a clean zero, not a division error, when nothing is scored.
    assert str(result.satisfaction_average) == "0"
    assert "satisfaction" in build_export_csv(result)
