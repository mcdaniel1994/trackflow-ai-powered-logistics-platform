from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from incident_processor.main import create_app
from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME

FIXTURE = Path(__file__).parent / "fixtures" / "sample-incidents.csv"


@pytest.fixture
def key_pair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture
def client(monkeypatch, key_pair):
    _private_pem, public_pem = key_pair
    monkeypatch.setenv("IDENTITY_JWT_PUBLIC_KEY", public_pem)
    return TestClient(create_app())


def authenticate(client: TestClient, private_key: str, *, must_change_password: bool = False) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "test-user",
        "role": "user",
        "status": "active",
        "must_change_password": must_change_password,
        "iss": "trackflow-identity",
        "aud": "trackflow-backoffice",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "jti": "incident-test-token",
        "token_type": "access",
    }
    token = jwt.encode(claims, private_key, algorithm="RS256")
    csrf_token = "incident-csrf-token"
    client.cookies.set(ACCESS_COOKIE_NAME, token)
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
    return {CSRF_HEADER_NAME: csrf_token}


def test_health_and_unauthenticated_business_routes(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/incidents/results/export").status_code == 401


def test_authenticated_no_last_analysis_export(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem)

    response = client.get("/api/incidents/results/export")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NO_ANALYSIS_AVAILABLE"


def test_health_and_no_last_analysis_export():
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/api/incidents/results/export")

    assert response.status_code == 401


def test_default_cors_allows_local_backoffice_origin(client: TestClient):
    response = client.options(
        "/api/incidents/analyze",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_analyze_stores_latest_result_and_export_returns_csv(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    csrf_headers = authenticate(client, private_pem)

    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/incidents/analyze",
            files={"file": ("sample-incidents.csv", handle, "text/csv")},
            headers=csrf_headers,
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


def test_api_errors_are_safe_and_do_not_leak_values(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    csrf_headers = authenticate(client, private_pem)

    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("bad.csv", b"incident_id,date\nprivate@example.com,broken\n", "text/csv")},
        headers=csrf_headers,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "MISSING_HEADERS"
    assert "private@example.com" not in str(body)


def test_request_validation_errors_do_not_echo_sensitive_inputs(
    client: TestClient,
    key_pair,
    caplog: pytest.LogCaptureFixture,
):
    private_pem, _public_pem = key_pair
    csrf_headers = authenticate(client, private_pem)
    sensitive_email = "private@example.com"
    sensitive_token = "incident-upload-token-secret"

    response = client.post(
        "/api/incidents/analyze",
        data={"file": sensitive_email, "token": sensitive_token},
        headers=csrf_headers,
    )

    assert response.status_code == 422
    serialized = response.text
    assert "input" not in serialized
    assert "ctx" not in serialized
    assert sensitive_email not in serialized
    assert sensitive_token not in serialized
    assert sensitive_email not in caplog.text
    assert sensitive_token not in caplog.text


def test_analyze_requires_csrf(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem)

    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/incidents/analyze",
            files={"file": ("sample-incidents.csv", handle, "text/csv")},
        )

    assert response.status_code == 403


def test_must_change_password_token_is_forbidden(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem, must_change_password=True)

    response = client.get("/api/incidents/results/export")

    assert response.status_code == 403


def test_custom_cors_origins_env_is_parsed_as_comma_list(monkeypatch, key_pair):
    _private_pem, public_pem = key_pair
    from incident_processor.config import get_cors_origins

    monkeypatch.setenv("IDENTITY_JWT_PUBLIC_KEY", public_pem)
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
