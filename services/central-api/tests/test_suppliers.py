"""Supplier contract, privacy, validation, and mutation regressions."""

from fastapi.testclient import TestClient


def payload() -> dict[str, object]:
    return {
        "name": "Privacy Safe Carrier",
        "country": "USA",
        "categories": ["carrier_last_mile"],
        "rate_per_shipment": 7.5,
        "currency": "USD",
        "status": "active",
        "contact_email": "private@example.test",
        "notes": None,
    }


def test_supplier_routes_require_auth(client: TestClient) -> None:
    assert client.get("/suppliers").status_code == 401


def test_create_list_detail_and_contact_preserve_privacy(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post("/suppliers", json=payload(), headers=auth_headers)
    assert created.status_code == 201
    supplier = created.json()
    assert supplier["has_contact_email"] is True
    assert "contact_email" not in supplier
    assert "private@example.test" not in created.text

    listed = client.get("/suppliers?country=USA&category=carrier_last_mile", headers=auth_headers)
    assert [item["id"] for item in listed.json()] == [supplier["id"]]
    assert client.get(f"/suppliers/{supplier['id']}", headers=auth_headers).json() == supplier
    contact = client.get(f"/suppliers/{supplier['id']}/contact", headers=auth_headers)
    assert contact.json() == {"id": supplier["id"], "contact_email": "private@example.test"}


def test_supplier_validation_duplicate_and_missing_contracts(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.post("/suppliers", json={**payload(), "currency": "EUR"}, headers=auth_headers).status_code == 422
    assert client.post("/suppliers", json=payload(), headers=auth_headers).status_code == 201
    duplicate = client.post("/suppliers", json=payload(), headers=auth_headers)
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "A supplier with that name and country already exists"}
    assert client.get("/suppliers/missing", headers=auth_headers).status_code == 404


def test_cookie_writes_require_csrf(client: TestClient, cookie_auth: object) -> None:
    authenticate = cookie_auth
    assert callable(authenticate)
    authenticate(csrf=False)
    assert client.post("/suppliers", json=payload()).status_code == 403
