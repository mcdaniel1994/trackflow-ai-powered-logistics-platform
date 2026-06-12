from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from incident_processor.main import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sample-incidents.csv"


def test_health_and_no_last_analysis_export():
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/api/incidents/results/export")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NO_ANALYSIS_AVAILABLE"


def test_default_cors_allows_local_backoffice_origin():
    client = TestClient(create_app())

    response = client.options(
        "/api/incidents/analyze",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_analyze_stores_latest_result_and_export_returns_csv():
    client = TestClient(create_app())

    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/incidents/analyze",
            files={"file": ("sample-incidents.csv", handle, "text/csv")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_records"] == 100
    assert payload["valid_records"] == 95
    assert "@example.com" not in str(payload)

    export = client.get("/api/incidents/results/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "summary,total_records,100," in export.text
    assert "@example.com" not in export.text


def test_api_errors_are_safe_and_do_not_leak_values():
    client = TestClient(create_app())
    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("bad.csv", b"incident_id,date\nprivate@example.com,broken\n", "text/csv")},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "MISSING_HEADERS"
    assert "private@example.com" not in str(body)


def test_custom_cors_origins_env_is_parsed_as_comma_list(monkeypatch):
    from incident_processor.config import get_cors_origins

    monkeypatch.setenv(
        "INCIDENT_PROCESSOR_CORS_ORIGINS",
        "https://backoffice.trackflow.example, http://localhost:4000 ,",
    )

    assert get_cors_origins() == [
        "https://backoffice.trackflow.example",
        "http://localhost:4000",
    ]

    client = TestClient(create_app())
    response = client.options(
        "/api/incidents/analyze",
        headers={
            "Origin": "https://backoffice.trackflow.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://backoffice.trackflow.example"
    )
