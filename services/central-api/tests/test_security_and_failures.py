"""Token rejection and safe database-failure behavior."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from central_api.db.session import get_session


@pytest.mark.parametrize(
    "token_kwargs",
    [
        {"audience": "wrong-audience"},
        {"expires_delta": timedelta(seconds=-1)},
        {"status": "disabled"},
    ],
)
def test_invalid_identity_claims_are_rejected(
    client: TestClient,
    token_factory: Any,
    token_kwargs: dict[str, object],
) -> None:
    token = token_factory(**token_kwargs)
    response = client.get("/inventory/products", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_tampered_token_is_rejected(client: TestClient, token_factory: Any) -> None:
    token = token_factory()
    header, payload, signature = token.split(".")
    tampered_signature = f"{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"
    tampered = f"{header}.{payload}.{tampered_signature}"
    response = client.get("/inventory/products", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


class BrokenSession:
    """Minimal session double that fails before any payload reaches a driver."""

    def execute(self, _statement: object) -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("postgresql://secret-user:secret-password@host/db"))

    def scalar(self, _statement: object) -> None:
        raise OperationalError("SELECT count", {}, RuntimeError("secret-payload"))

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


def test_database_failure_is_safe_in_response_and_logs(
    app: FastAPI,
    token_factory: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken_session() -> Generator[BrokenSession, None, None]:
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session
    secret_token = token_factory()
    caplog.set_level("ERROR")
    with TestClient(app) as test_client:
        response = test_client.get(
            "/inventory/products",
            headers={"Authorization": f"Bearer {secret_token}"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Inventory service temporarily unavailable"}
    combined = response.text + caplog.text
    assert "secret-password" not in combined
    assert "secret-payload" not in combined
    assert secret_token not in combined
    assert "postgresql://" not in combined


def test_health_database_failure_is_safe(app: FastAPI, caplog: pytest.LogCaptureFixture) -> None:
    def broken_session() -> Generator[BrokenSession, None, None]:
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session
    caplog.set_level("ERROR")
    with TestClient(app) as test_client:
        response = test_client.get("/health")
        ready = test_client.get("/health/ready")
        live = test_client.get("/health/live")

    assert response.status_code == 503
    assert response.json() == {"detail": "Inventory database unavailable"}
    assert ready.status_code == 503
    assert ready.json() == {"status": "not_ready"}
    assert live.status_code == 200
    assert "secret-password" not in caplog.text
