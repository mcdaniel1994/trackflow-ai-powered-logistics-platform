from __future__ import annotations

from collections.abc import Generator

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from identity.main import create_app
from trackflow_auth import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


@pytest.fixture
def key_pair() -> tuple[str, str]:
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
def client(tmp_path, monkeypatch, key_pair) -> Generator[TestClient, None, None]:
    private_pem, public_pem = key_pair
    monkeypatch.setenv("IDENTITY_DB_PATH", str(tmp_path / "identity.json"))
    monkeypatch.setenv("IDENTITY_JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("IDENTITY_JWT_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("IDENTITY_JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("IDENTITY_JWT_ISSUER", "trackflow-identity")
    monkeypatch.setenv("IDENTITY_JWT_AUDIENCE", "trackflow-backoffice")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "14")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with TestClient(create_app()) as test_client:
        yield test_client


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE_NAME)
    assert token
    return {CSRF_HEADER_NAME: token}


def create_admin(client: TestClient, email: str = "Admin@TrackFlow.test", password: str = "admin-passphrase") -> dict:
    return client.app.state.user_service.create_admin(
        name="Admin User",
        email=email,
        password=password,
    ).model_dump(mode="json")


def login(client: TestClient, email: str, password: str) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()
