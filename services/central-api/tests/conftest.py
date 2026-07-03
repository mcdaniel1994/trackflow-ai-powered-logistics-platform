"""Shared disposable-PostgreSQL and Identity-token fixtures."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, create_engine
from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME  # type: ignore[import-untyped]

from central_api.core.config import Settings, get_settings
from central_api.db.session import get_session
from central_api.main import create_app

TokenFactory = Callable[..., str]


@pytest.fixture(scope="session")
def database_url() -> str:
    """Refuse to run destructive test cleanup against anything but local Compose."""
    url = get_settings().database_url
    parsed = make_url(url)
    if parsed.host not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        raise RuntimeError("Central API tests require the disposable local PostgreSQL on port 55432")
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


@pytest.fixture(autouse=True)
def clean_database(engine: Engine) -> Generator[None, None, None]:
    """Give every test deterministic tables without bypassing Alembic schema ownership."""
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE suppliers, incidents, stock_exits, stock_entries, skus RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture(scope="session")
def signing_keys() -> tuple[str, str]:
    """Generate an isolated RS256 keypair; no repository or Identity secret is reused."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
def settings(database_url: str, signing_keys: tuple[str, str]) -> Settings:
    return Settings(database_url=database_url, identity_jwt_public_key=signing_keys[1])


@pytest.fixture
def token_factory(signing_keys: tuple[str, str]) -> TokenFactory:
    private_key = signing_keys[0]

    def create_token(
        *,
        user_id: str = "11111111-1111-4111-8111-111111111111",
        audience: str = "trackflow-backoffice",
        expires_delta: timedelta = timedelta(minutes=10),
        must_change_password: bool = False,
        status: str = "active",
    ) -> str:
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "sub": user_id,
            "role": "user",
            "status": status,
            "must_change_password": must_change_password,
            "iss": "trackflow-identity",
            "aud": audience,
            "exp": now + expires_delta,
            "iat": now,
            "jti": str(uuid4()),
            "token_type": "access",
        }
        return str(jwt.encode(claims, private_key, algorithm="RS256"))

    return create_token


@pytest.fixture
def app(engine: Engine, settings: Settings) -> FastAPI:
    test_app = create_app()

    def session_override() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = session_override
    test_app.dependency_overrides[get_settings] = lambda: settings
    return test_app


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(token_factory: TokenFactory) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_factory()}"}


@pytest.fixture
def cookie_auth(client: TestClient, token_factory: TokenFactory) -> Callable[..., dict[str, str]]:
    def authenticate(*, csrf: bool = True, must_change_password: bool = False) -> dict[str, str]:
        client.cookies.set(ACCESS_COOKIE_NAME, token_factory(must_change_password=must_change_password))
        if not csrf:
            return {}
        token = "test-csrf-token"
        client.cookies.set(CSRF_COOKIE_NAME, token)
        return {CSRF_HEADER_NAME: token}

    return authenticate


@pytest.fixture
def product_payload() -> dict[str, object]:
    return {
        "name": "Classic White Sneaker - Size 42",
        "sku": "CLT-SNK-W-42",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "LA",
    }


@pytest.fixture
def incident_payload() -> dict[str, object]:
    return {
        "title": "Carrier missed delivery window",
        "description": "The assigned carrier missed the committed delivery window.",
        "category": "carrier_issue",
        "origin": "branch",
        "branch": "la_office",
    }


@pytest.fixture
def created_product(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
) -> dict[str, object]:
    response = client.post("/inventory/products", json=product_payload, headers=auth_headers)
    assert response.status_code == 201
    return response.json()
