"""Authoritative discrepancy occurrence API and database-invariant tests."""

from fastapi.testclient import TestClient


def _create_exit(
    client: TestClient,
    headers: dict[str, str],
    sku_id: object,
    *,
    exit_type: str = "dispatch",
) -> dict[str, object]:
    assert client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 10, "reference": "DISC-IN", "warehouse": "LA"},
        headers=headers,
    ).status_code == 201
    response = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 2,
            "exit_type": exit_type,
            "tracking_number": "DISC-TRACK" if exit_type == "dispatch" else None,
            "warehouse": "LA",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_discrepancy_creation_and_one_occurrence_per_dispatch(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    stock_exit = _create_exit(client, auth_headers, created_product["id"])
    created = client.post(
        "/inventory/discrepancies",
        json={"stock_exit_id": stock_exit["id"], "quantity_delta": -2},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["stock_exit_id"] == stock_exit["id"]
    assert created.json()["client_id"] == created_product["client_id"]
    assert created.json()["source"] == "manual"

    duplicate = client.post(
        "/inventory/discrepancies",
        json={"stock_exit_id": stock_exit["id"], "quantity_delta": 1},
        headers=auth_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "DISCREPANCY_EXISTS"}


def test_discrepancy_rejects_unknown_loss_and_zero_delta(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    unknown = client.post(
        "/inventory/discrepancies",
        json={"stock_exit_id": 9999, "quantity_delta": 1},
        headers=auth_headers,
    )
    assert unknown.status_code == 404

    loss = _create_exit(client, auth_headers, created_product["id"], exit_type="loss")
    wrong_type = client.post(
        "/inventory/discrepancies",
        json={"stock_exit_id": loss["id"], "quantity_delta": 1},
        headers=auth_headers,
    )
    assert wrong_type.status_code == 422
    assert wrong_type.json() == {"detail": "Discrepancy requires a dispatch stock exit"}

    zero = client.post(
        "/inventory/discrepancies",
        json={"stock_exit_id": loss["id"], "quantity_delta": 0},
        headers=auth_headers,
    )
    assert zero.status_code == 422
