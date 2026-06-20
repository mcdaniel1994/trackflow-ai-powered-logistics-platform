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
        "jti": "supplier-test-token",
        "token_type": "access",
    }
    token = jwt.encode(claims, private_key, algorithm="RS256")
    csrf_token = "supplier-csrf-token"
    client.cookies.set(ACCESS_COOKIE_NAME, token)
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
    return {CSRF_HEADER_NAME: csrf_token}


def test_health_and_list_seeded_suppliers_without_raw_email(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/suppliers").status_code == 401


def test_authenticated_list_seeded_suppliers_without_raw_email(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem)

    response = client.get("/suppliers")
    assert response.status_code == 200
    suppliers = response.json()

    assert len(suppliers) == 15
    assert all("has_contact_email" in supplier for supplier in suppliers)
    assert all("contact_email" not in supplier for supplier in suppliers)
    assert "business@ups.com" not in str(suppliers)


def test_list_filters_by_country_and_category(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem)

    usa = client.get("/suppliers?country=USA").json()
    reverse_logistics = client.get("/suppliers?category=reverse_logistics").json()

    assert len(usa) == 9
    assert {supplier["country"] for supplier in usa} == {"USA"}
    assert len(reverse_logistics) == 2
    assert all("reverse_logistics" in supplier["categories"] for supplier in reverse_logistics)


def test_detail_hides_email_and_contact_endpoint_returns_raw_email(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem)

    supplier_id = client.get("/suppliers").json()[0]["id"]

    detail = client.get(f"/suppliers/{supplier_id}")
    contact = client.get(f"/suppliers/{supplier_id}/contact")

    assert detail.status_code == 200
    assert "contact_email" not in detail.json()
    assert detail.json()["has_contact_email"] is True
    assert contact.status_code == 200
    assert contact.json()["contact_email"]
    assert "@" in contact.json()["contact_email"]


def test_get_missing_supplier_returns_404(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem)

    response = client.get("/suppliers/missing")

    assert response.status_code == 404


def test_patch_rate_updates_value_and_timestamp(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    csrf_headers = authenticate(client, private_pem)
    supplier = client.get("/suppliers").json()[0]
    original_timestamp = datetime.fromisoformat(supplier["rate_updated_at"])

    response = client.patch(
        f"/suppliers/{supplier['id']}/rate",
        json={"rate_per_shipment": 9.99},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    updated = response.json()
    updated_timestamp = datetime.fromisoformat(updated["rate_updated_at"])
    assert updated["rate_per_shipment"] == 9.99
    assert updated_timestamp >= original_timestamp
    assert updated["rate_updated_at"] != supplier["rate_updated_at"]


def test_patch_status_requires_csrf(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem)
    supplier = client.get("/suppliers").json()[0]

    response = client.patch(f"/suppliers/{supplier['id']}/status", json={"status": "suspended"})

    assert response.status_code == 403


def test_patch_status_rejects_invalid_status(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    csrf_headers = authenticate(client, private_pem)
    supplier = client.get("/suppliers").json()[0]

    response = client.patch(
        f"/suppliers/{supplier['id']}/status",
        json={"status": "paused"},
        headers=csrf_headers,
    )

    assert response.status_code == 422


def test_patch_status_updates_supplier(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    csrf_headers = authenticate(client, private_pem)
    supplier = client.get("/suppliers").json()[0]

    response = client.patch(
        f"/suppliers/{supplier['id']}/status",
        json={"status": "suspended"},
        headers=csrf_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "suspended"


def test_delete_missing_supplier_returns_404(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    csrf_headers = authenticate(client, private_pem)

    response = client.delete("/suppliers/missing", headers=csrf_headers)

    assert response.status_code == 404


def test_must_change_password_token_is_forbidden(client: TestClient, key_pair):
    private_pem, _public_pem = key_pair
    authenticate(client, private_pem, must_change_password=True)

    response = client.get("/suppliers")

    assert response.status_code == 403
