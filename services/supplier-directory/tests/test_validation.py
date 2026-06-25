from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from supplier_directory.main import create_app
from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME


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
def client(tmp_path, monkeypatch, key_pair):
    _private_pem, public_pem = key_pair
    monkeypatch.setenv("SUPPLIER_DIRECTORY_DB_PATH", str(tmp_path / "suppliers.json"))
    monkeypatch.setenv("IDENTITY_JWT_PUBLIC_KEY", public_pem)
    with TestClient(create_app()) as test_client:
        yield test_client


def authenticate(client: TestClient, private_key: str) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "validation-test-user",
        "role": "user",
        "status": "active",
        "must_change_password": False,
        "iss": "trackflow-identity",
        "aud": "trackflow-backoffice",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "jti": "supplier-validation-token",
        "token_type": "access",
    }
    csrf_token = "supplier-validation-csrf"
    client.cookies.set(ACCESS_COOKIE_NAME, jwt.encode(claims, private_key, algorithm="RS256"))
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
    return {CSRF_HEADER_NAME: csrf_token}


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Test Supplier",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 3.25,
        "currency": "USD",
        "status": "active",
        "service_zone": "West Coast",
        "contact_email": "ops@example.com",
        "notes": "Synthetic test supplier.",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "paused"},
        {"categories": ["not_a_category"]},
        {"currency": "GBP"},
        {"rate_per_shipment": 0},
        {"rate_per_shipment": -1},
        {"country": "USA", "currency": "EUR"},
        {"country": "Spain", "currency": "USD"},
        {"categories": []},
    ],
)
def test_create_supplier_rejects_invalid_payloads(client: TestClient, key_pair, overrides: dict[str, object]):
    private_pem, _public_pem = key_pair
    response = client.post(
        "/suppliers",
        json=valid_payload(**overrides),
        headers=authenticate(client, private_pem),
    )

    assert response.status_code == 422


def test_create_supplier_validation_does_not_echo_sensitive_inputs(
    client: TestClient,
    key_pair,
    caplog: pytest.LogCaptureFixture,
):
    private_pem, _public_pem = key_pair
    sensitive_email = "supplier-secret@example.com"
    sensitive_token = "supplier-reset-token-secret"

    response = client.post(
        "/suppliers",
        json=valid_payload(
            status="paused",
            contact_email=sensitive_email,
            notes=f"Escalation token: {sensitive_token}",
        ),
        headers=authenticate(client, private_pem),
    )

    assert response.status_code == 422
    serialized = response.text
    assert "input" not in serialized
    assert "ctx" not in serialized
    assert sensitive_email not in serialized
    assert sensitive_token not in serialized
    assert sensitive_email not in caplog.text
    assert sensitive_token not in caplog.text
