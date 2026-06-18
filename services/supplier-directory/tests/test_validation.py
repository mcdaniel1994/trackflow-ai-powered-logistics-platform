from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from supplier_directory.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPLIER_DIRECTORY_DB_PATH", str(tmp_path / "suppliers.json"))
    with TestClient(create_app()) as test_client:
        yield test_client


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
def test_create_supplier_rejects_invalid_payloads(client: TestClient, overrides: dict[str, object]):
    response = client.post("/suppliers", json=valid_payload(**overrides))

    assert response.status_code == 422
