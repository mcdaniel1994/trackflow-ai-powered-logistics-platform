"""Centralized incident API lifecycle, validation, filtering, and summary tests."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.domains.incidents.models import Incident
from central_api.domains.incidents.seed import main as seed_main
from central_api.domains.incidents.seed import seed_incidents

FIXTURE = (
    Path(__file__).parents[2] / "incident-processor" / "tests" / "fixtures" / "sample-incidents.csv"
)


def create_incident(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, object],
) -> dict[str, object]:
    response = client.post("/api/incidents", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_defaults_and_reporter(
    client: TestClient,
    auth_headers: dict[str, str],
    incident_payload: dict[str, object],
) -> None:
    created = create_incident(client, auth_headers, incident_payload)

    assert created["status"] == "open"
    assert created["created_by_user_uuid"] == "11111111-1111-4111-8111-111111111111"
    assert created["created_at"].endswith("Z")
    assert created["updated_at"].endswith("Z")


def test_incident_routes_require_auth_and_cookie_writes_require_csrf(
    client: TestClient,
    cookie_auth: object,
    incident_payload: dict[str, object],
) -> None:
    assert client.get("/api/incidents").status_code == 401
    authenticate = cookie_auth
    assert callable(authenticate)
    authenticate(csrf=False)
    assert client.post("/api/incidents", json=incident_payload).status_code == 403


def test_validation_returns_field_keyed_400(
    client: TestClient,
    auth_headers: dict[str, str],
    incident_payload: dict[str, object],
) -> None:
    payload = {**incident_payload}
    payload.pop("title")
    response = client.post("/api/incidents", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["fields"] == {"title": "Field is required."}
    assert "input" not in response.text


def test_list_filters_paginates_and_gets_detail(
    client: TestClient,
    auth_headers: dict[str, str],
    incident_payload: dict[str, object],
) -> None:
    first = create_incident(client, auth_headers, incident_payload)
    create_incident(
        client,
        auth_headers,
        {
            **incident_payload,
            "title": "Warehouse stock mismatch",
            "category": "inventory_discrepancy",
            "origin": "internal",
            "branch": "zaragoza_warehouse",
        },
    )

    response = client.get(
        "/api/incidents?category=carrier_issue&origin=branch&limit=1&offset=0",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [first["id"]]
    assert client.get(f"/api/incidents/{first['id']}", headers=auth_headers).json() == first
    assert client.get("/api/incidents/9999", headers=auth_headers).status_code == 404


def test_status_lifecycle_and_final_states(
    client: TestClient,
    auth_headers: dict[str, str],
    incident_payload: dict[str, object],
) -> None:
    created = create_incident(client, auth_headers, incident_payload)
    incident_id = created["id"]

    invalid = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "resolved"},
        headers=auth_headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["fields"]["status"].startswith("Status cannot change")

    progressing = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert progressing.status_code == 200
    resolved = client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "resolved"},
        headers=auth_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert client.patch(
        f"/api/incidents/{incident_id}/status",
        json={"status": "discarded"},
        headers=auth_headers,
    ).status_code == 400


def test_summary_includes_zero_keys_and_current_counts(
    client: TestClient,
    auth_headers: dict[str, str],
    incident_payload: dict[str, object],
) -> None:
    empty = client.get("/api/incidents/summary", headers=auth_headers).json()
    assert empty["total"] == 0
    assert empty["by_status"] == {"open": 0, "in_progress": 0, "resolved": 0, "discarded": 0}
    assert empty["by_category"]["lost_parcel"] == 0
    assert empty["by_branch"]["zaragoza_office"] == 0

    create_incident(client, auth_headers, incident_payload)
    summary = client.get("/api/incidents/summary", headers=auth_headers).json()
    assert summary["total"] == 1
    assert summary["by_status"]["open"] == 1
    assert summary["by_category"]["carrier_issue"] == 1


def test_seed_is_repeatable_and_preserves_historical_defaults(engine: Engine) -> None:
    with Session(engine) as session:
        first = seed_incidents(FIXTURE, session)
        second = seed_incidents(FIXTURE, session)
        rows = list(session.exec(select(Incident)).all())

    assert first.inserted == first.total_records - first.invalid_records
    assert second.inserted == 0
    assert second.skipped == first.inserted
    assert all(row.origin == "customer" and row.branch == "central" for row in rows)
    assert all(row.created_by_user_uuid is None for row in rows)
    assert all(row.import_key_hash and len(row.import_key_hash) == 64 for row in rows)
    assert all(row.created_at.hour == 0 and row.created_at.minute == 0 for row in rows)


def test_seed_cli_reports_safe_file_error(
    tmp_path: Path,
    capsys: object,
) -> None:
    missing = tmp_path / "missing.csv"
    assert seed_main([str(missing)]) == 1
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert captured.out == "Import failed: FILE_READ_ERROR\n"
    assert str(missing) not in captured.out


def test_seed_cli_reports_aggregate_counts_without_rows(
    capsys: object,
) -> None:
    assert seed_main([str(FIXTURE)]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "Incident seed complete: inserted=" in captured.out
    assert "private@" not in captured.out
