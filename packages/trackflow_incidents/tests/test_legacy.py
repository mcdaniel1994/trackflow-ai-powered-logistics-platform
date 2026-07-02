from trackflow_incidents import IncidentCategory, IncidentStatus, normalize_legacy_incident, parse_legacy_csv


def test_parses_and_normalizes_without_retaining_email() -> None:
    payload = (
        b"incident_id,date,country,customer_type,tracking_number,carrier,category,description,status,"
        b"customer_email,satisfaction_score\n"
        b"TRF-000001,2026-05-01,US,B2C,USTRACK000001,UPS,DAMAGE,Package arrived damaged,CLOSED,"
        b"private@example.com,5\n"
    )
    result = parse_legacy_csv(payload)
    normalized = normalize_legacy_incident(result.valid_rows[0])

    assert result.total_records == 1
    assert result.invalid_records == 0
    assert normalized.category is IncidentCategory.CARRIER_ISSUE
    assert normalized.status is IncidentStatus.RESOLVED
    assert "private@example.com" not in repr(result)
    assert "TRF-000001" not in normalized.title


def test_invalid_rows_report_only_safe_location_and_code() -> None:
    payload = (
        b"incident_id,date,country,customer_type,tracking_number,carrier,category,description,status,"
        b"customer_email,satisfaction_score\n"
        b"bad,not-a-date,US,B2C,x,UPS,NOPE,no,OPEN,private-value,\n"
    )
    result = parse_legacy_csv(payload)

    assert result.valid_rows == ()
    assert result.invalid_records == 1
    assert {error.field for error in result.errors} >= {"incident_id", "date", "category"}
    assert "private-value" not in repr(result.errors)
