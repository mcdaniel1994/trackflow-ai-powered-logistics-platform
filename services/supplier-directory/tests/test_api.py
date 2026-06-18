from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from supplier_directory.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPLIER_DIRECTORY_DB_PATH", str(tmp_path / "suppliers.json"))
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_and_list_seeded_suppliers_without_raw_email(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}

    response = client.get("/suppliers")
    assert response.status_code == 200
    suppliers = response.json()

    assert len(suppliers) == 15
    assert all("has_contact_email" in supplier for supplier in suppliers)
    assert all("contact_email" not in supplier for supplier in suppliers)
    assert "business@ups.com" not in str(suppliers)


def test_list_filters_by_country_and_category(client: TestClient):
    usa = client.get("/suppliers?country=USA").json()
    reverse_logistics = client.get("/suppliers?category=reverse_logistics").json()

    assert len(usa) == 9
    assert {supplier["country"] for supplier in usa} == {"USA"}
    assert len(reverse_logistics) == 2
    assert all("reverse_logistics" in supplier["categories"] for supplier in reverse_logistics)


def test_detail_hides_email_and_contact_endpoint_returns_raw_email(client: TestClient):
    supplier_id = client.get("/suppliers").json()[0]["id"]

    detail = client.get(f"/suppliers/{supplier_id}")
    contact = client.get(f"/suppliers/{supplier_id}/contact")

    assert detail.status_code == 200
    assert "contact_email" not in detail.json()
    assert detail.json()["has_contact_email"] is True
    assert contact.status_code == 200
    assert contact.json()["contact_email"]
    assert "@" in contact.json()["contact_email"]


def test_get_missing_supplier_returns_404(client: TestClient):
    response = client.get("/suppliers/missing")

    assert response.status_code == 404


def test_patch_rate_updates_value_and_timestamp(client: TestClient):
    supplier = client.get("/suppliers").json()[0]
    original_timestamp = datetime.fromisoformat(supplier["rate_updated_at"])

    response = client.patch(
        f"/suppliers/{supplier['id']}/rate",
        json={"rate_per_shipment": 9.99},
    )

    assert response.status_code == 200
    updated = response.json()
    updated_timestamp = datetime.fromisoformat(updated["rate_updated_at"])
    assert updated["rate_per_shipment"] == 9.99
    assert updated_timestamp >= original_timestamp
    assert updated["rate_updated_at"] != supplier["rate_updated_at"]


def test_patch_status_rejects_invalid_status(client: TestClient):
    supplier = client.get("/suppliers").json()[0]

    response = client.patch(f"/suppliers/{supplier['id']}/status", json={"status": "paused"})

    assert response.status_code == 422


def test_patch_status_updates_supplier(client: TestClient):
    supplier = client.get("/suppliers").json()[0]

    response = client.patch(f"/suppliers/{supplier['id']}/status", json={"status": "suspended"})

    assert response.status_code == 200
    assert response.json()["status"] == "suspended"


def test_delete_missing_supplier_returns_404(client: TestClient):
    response = client.delete("/suppliers/missing")

    assert response.status_code == 404
