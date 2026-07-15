"""End-to-end inventory contract tests against disposable PostgreSQL."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.domains.inventory.repository import exit_table


def test_health_checks_database(client: TestClient, engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reporting.worker_heartbeats "
                "(worker_name, heartbeat_at, last_progress_at, orchestrator_healthy) "
                "VALUES ('reporting', now(), now(), true)"
            )
        )
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready"}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/inventory/products", None),
        ("GET", "/inventory/clients", None),
        ("POST", "/inventory/clients", {}),
        ("PATCH", "/inventory/clients/11111111-1111-4111-8111-111111111111", {}),
        ("POST", "/inventory/products", {}),
        ("PATCH", "/inventory/products/1", {}),
        ("GET", "/inventory/products/1", None),
        ("POST", "/inventory/orders/inbound", {}),
        ("POST", "/inventory/orders/outbound", {}),
        ("POST", "/inventory/discrepancies", {}),
        ("GET", "/inventory/orders", None),
    ],
)
def test_every_inventory_route_requires_authentication(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_create_get_and_paginate_products(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
) -> None:
    created = client.post("/inventory/products", json=product_payload, headers=auth_headers)
    assert created.status_code == 201
    assert created.json()["current_stock"] == 0
    assert "user_uuid" not in created.json()

    fetched = client.get(f"/inventory/products/{created.json()['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json() == created.json()

    page = client.get("/inventory/products?limit=1&offset=0", headers=auth_headers)
    assert page.status_code == 200
    assert page.json()["total"] == 1
    assert page.json()["items"] == [created.json()]
    assert page.json()["limit"] == 1


def test_duplicate_sku_is_scoped_by_warehouse(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
) -> None:
    assert client.post("/inventory/products", json=product_payload, headers=auth_headers).status_code == 201
    duplicate = client.post("/inventory/products", json=product_payload, headers=auth_headers)
    assert duplicate.status_code == 409

    zaragoza = {**product_payload, "warehouse": "ZGZ"}
    assert client.post("/inventory/products", json=zaragoza, headers=auth_headers).status_code == 201


def test_stock_is_computed_per_warehouse_for_same_sku_code(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
) -> None:
    la = client.post("/inventory/products", json=product_payload, headers=auth_headers).json()
    zgz = client.post(
        "/inventory/products",
        json={**product_payload, "warehouse": "ZGZ"},
        headers=auth_headers,
    ).json()

    for sku_id, warehouse, quantity in ((la["id"], "LA", 20), (zgz["id"], "ZGZ", 15)):
        response = client.post(
            "/inventory/orders/inbound",
            json={"sku_id": sku_id, "quantity": quantity, "reference": f"GR-{warehouse}", "warehouse": warehouse},
            headers=auth_headers,
        )
        assert response.status_code == 201

    assert client.get(f"/inventory/products/{la['id']}", headers=auth_headers).json()["current_stock"] == 20
    assert client.get(f"/inventory/products/{zgz['id']}", headers=auth_headers).json()["current_stock"] == 15


def test_inbound_outbound_timeline_and_server_owned_user(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    inbound = client.post(
        "/inventory/orders/inbound",
        json={"sku_id": created_product["id"], "quantity": 12, "reference": "PO-100", "warehouse": "LA"},
        headers=auth_headers,
    )
    assert inbound.status_code == 201
    assert inbound.json()["user_uuid"] == "11111111-1111-4111-8111-111111111111"

    outbound = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": created_product["id"],
            "quantity": 5,
            "exit_type": "dispatch",
            "tracking_number": "1Z999AA10123456784",
            "warehouse": "LA",
        },
        headers=auth_headers,
    )
    assert outbound.status_code == 201
    assert client.get(f"/inventory/products/{created_product['id']}", headers=auth_headers).json()["current_stock"] == 7

    timeline = client.get("/inventory/orders?limit=10&offset=0", headers=auth_headers)
    assert timeline.status_code == 200
    body = timeline.json()
    assert body["total"] == 2
    assert [item["movement_type"] for item in body["items"]] == ["outbound", "inbound"]
    assert body["items"][0]["sku"]["sku"] == "CLT-SNK-W-42"
    assert body["items"][0]["reference"] is None
    assert body["items"][1]["exit_type"] is None


def test_insufficient_stock_exact_message_and_no_write(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    engine: Engine,
) -> None:
    response = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": created_product["id"],
            "quantity": 1,
            "exit_type": "loss",
            "tracking_number": None,
            "warehouse": "LA",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Insufficient stock for SKU 'CLT-SNK-W-42'. Available: 0, requested: 1."
    }
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(exit_table)) == 0


def test_unknown_sku_and_warehouse_mismatch(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    unknown = client.post(
        "/inventory/orders/inbound",
        json={"sku_id": 9999, "quantity": 1, "reference": "PO-X", "warehouse": "LA"},
        headers=auth_headers,
    )
    assert unknown.status_code == 404

    mismatch = client.post(
        "/inventory/orders/inbound",
        json={"sku_id": created_product["id"], "quantity": 1, "reference": "PO-X", "warehouse": "ZGZ"},
        headers=auth_headers,
    )
    assert mismatch.status_code == 400
    assert mismatch.json() == {"detail": "Movement warehouse must match SKU warehouse"}


def test_cookie_writes_require_matching_csrf(
    client: TestClient,
    cookie_auth: Callable[..., dict[str, str]],
    product_payload: dict[str, object],
) -> None:
    cookie_auth(csrf=False)
    assert client.post("/inventory/products", json=product_payload).status_code == 403

    client.cookies.set("trackflow_csrf", "cookie-value")
    mismatched = client.post("/inventory/products", json=product_payload, headers={"X-CSRF-Token": "other"})
    assert mismatched.status_code == 403

    headers = cookie_auth()
    assert client.post("/inventory/products", json=product_payload, headers=headers).status_code == 201


def test_bearer_write_does_not_require_csrf(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
) -> None:
    assert client.post("/inventory/products", json=product_payload, headers=auth_headers).status_code == 201


def test_temporary_password_user_is_forbidden(
    client: TestClient,
    cookie_auth: Callable[..., dict[str, str]],
    product_payload: dict[str, object],
) -> None:
    headers = cookie_auth(must_change_password=True)
    response = client.post("/inventory/products", json=product_payload, headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Password change required"}


def test_user_uuid_and_current_stock_are_not_client_writable(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
    created_product: dict[str, object],
) -> None:
    product = client.post(
        "/inventory/products",
        json={**product_payload, "sku": "EXTRA", "current_stock": 100},
        headers=auth_headers,
    )
    assert product.status_code == 422
    assert "input" not in product.text

    movement = client.post(
        "/inventory/orders/inbound",
        json={
            "sku_id": created_product["id"],
            "quantity": 1,
            "reference": "PO-X",
            "warehouse": "LA",
            "user_uuid": "attacker-controlled",
        },
        headers=auth_headers,
    )
    assert movement.status_code == 422
    assert "attacker-controlled" not in movement.text
