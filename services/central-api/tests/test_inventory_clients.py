"""Client administration, UUID ownership, and threshold contract tests."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_client_list_create_rename_and_duplicate_conflict(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    forbidden = client.post("/inventory/clients", json={"display_name": "Admin Only"}, headers=auth_headers)
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "Administrator role required"}

    created = client.post("/inventory/clients", json={"display_name": "Beta Brand"}, headers=admin_headers)
    assert created.status_code == 201
    client_id = created.json()["client_id"]

    duplicate = client.post("/inventory/clients", json={"display_name": "Beta Brand"}, headers=admin_headers)
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "CLIENT_NAME_EXISTS"}

    renamed = client.patch(
        f"/inventory/clients/{client_id}",
        json={"display_name": "Alpha Brand"},
        headers=admin_headers,
    )
    assert renamed.status_code == 200
    assert renamed.json() == {"client_id": client_id, "client_name": "Alpha Brand"}

    listed = client.get("/inventory/clients", headers=auth_headers)
    assert listed.status_code == 200
    assert [item["client_name"] for item in listed.json()] == ["Alpha Brand"]


def test_product_requires_existing_client_and_uuid_is_immutable(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
    created_product: dict[str, object],
) -> None:
    missing_client = client.post(
        "/inventory/products",
        json={**product_payload, "sku": "UNKNOWN-CLIENT", "client_id": str(uuid4())},
        headers=auth_headers,
    )
    assert missing_client.status_code == 422
    assert missing_client.json() == {"detail": "Client not found"}

    reassignment = client.patch(
        f"/inventory/products/{created_product['id']}",
        json={"client_id": str(uuid4())},
        headers=auth_headers,
    )
    assert reassignment.status_code == 409
    assert reassignment.json() == {"detail": "CLIENT_ID_IMMUTABLE"}


def test_threshold_update_validation_and_client_rename_is_join_derived(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    invalid = client.patch(
        f"/inventory/products/{created_product['id']}",
        json={"min_stock_threshold": -1},
        headers=auth_headers,
    )
    assert invalid.status_code == 422

    updated = client.patch(
        f"/inventory/products/{created_product['id']}",
        json={"min_stock_threshold": 8},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["min_stock_threshold"] == 8

    client_id = created_product["client_id"]
    renamed = client.patch(
        f"/inventory/clients/{client_id}",
        json={"display_name": "PureStep Renamed"},
        headers=admin_headers,
    )
    assert renamed.status_code == 200
    fetched = client.get(f"/inventory/products/{created_product['id']}", headers=auth_headers)
    assert fetched.json()["client_name"] == "PureStep Renamed"
    assert fetched.json()["client_id"] == client_id


def test_client_and_product_update_not_found_and_duplicate_rename(
    client: TestClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    first = client.post("/inventory/clients", json={"display_name": "First"}, headers=admin_headers).json()
    second = client.post("/inventory/clients", json={"display_name": "Second"}, headers=admin_headers).json()

    duplicate = client.patch(
        f"/inventory/clients/{second['client_id']}",
        json={"display_name": "First"},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "CLIENT_NAME_EXISTS"}

    missing_client = client.patch(
        f"/inventory/clients/{uuid4()}",
        json={"display_name": "Missing"},
        headers=admin_headers,
    )
    assert missing_client.status_code == 404

    missing_product = client.patch(
        "/inventory/products/9999",
        json={"min_stock_threshold": 1},
        headers=auth_headers,
    )
    assert missing_product.status_code == 404
    assert client.get("/inventory/products/9999", headers=auth_headers).status_code == 404

    empty_update = client.patch("/inventory/products/9999", json={}, headers=auth_headers)
    assert empty_update.status_code == 422
    assert first["client_id"] != second["client_id"]
