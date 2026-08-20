"""Proofs that the materialized balance never disagrees with the movement ledger.

`spec.md` §8.4 requires any scheme that changes how stock is derived to prove
computed-stock correctness is preserved. `verify_stock_balances` re-derives every
balance from the ledger, so an empty drift list is that proof.
"""

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.domains.inventory.balances import (
    rebuild_stock_balances,
    verify_stock_balances,
)


def _drift(engine: Engine) -> list[object]:
    with Session(engine) as session:
        return list(verify_stock_balances(session))


def test_inbound_and_outbound_keep_the_balance_equal_to_the_ledger(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    sku_id = created_product["id"]
    assert client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 25, "reference": "BAL-IN", "warehouse": "LA"},
        headers=auth_headers,
    ).status_code == 201
    assert client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 10,
            "exit_type": "dispatch",
            "tracking_number": "BAL-OUT",
            "warehouse": "LA",
        },
        headers=auth_headers,
    ).status_code == 201

    assert client.get(f"/inventory/products/{sku_id}", headers=auth_headers).json()["current_stock"] == 15
    assert _drift(engine) == []


def test_rejected_outbound_leaves_the_balance_untouched(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    """A refused dispatch rolls back; the balance must not absorb the attempt."""
    sku_id = created_product["id"]
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 5, "reference": "BAL-SMALL", "warehouse": "LA"},
        headers=auth_headers,
    )
    rejected = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 500,
            "exit_type": "dispatch",
            "tracking_number": "BAL-TOOBIG",
            "warehouse": "LA",
        },
        headers=auth_headers,
    )
    assert rejected.status_code == 400
    assert client.get(f"/inventory/products/{sku_id}", headers=auth_headers).json()["current_stock"] == 5
    assert _drift(engine) == []


def test_rebuild_repairs_a_deliberately_corrupted_balance(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    """The bulk-path rebuild must restore exact agreement, and the verifier must
    have detected the corruption in the first place -- otherwise it proves nothing."""
    from sqlalchemy import text

    sku_id = created_product["id"]
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 40, "reference": "BAL-REBUILD", "warehouse": "LA"},
        headers=auth_headers,
    )

    with Session(engine) as session:
        session.execute(
            text("UPDATE stock_balances SET quantity = quantity + 999 WHERE sku_id = :id"),
            {"id": sku_id},
        )
        session.commit()

    # The verifier must actually catch it.
    drifted = _drift(engine)
    assert len(drifted) == 1

    with Session(engine) as session:
        rebuild_stock_balances(session)
        session.commit()

    assert _drift(engine) == []
    assert client.get(f"/inventory/products/{sku_id}", headers=auth_headers).json()["current_stock"] == 40
