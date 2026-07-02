"""Boundary validation and PostgreSQL invariant tests."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from central_api.domains.inventory.models import SKU, StockEntry, StockExit


@pytest.mark.parametrize(
    "payload",
    [
        {"sku_id": 1, "quantity": 1, "exit_type": "dispatch", "tracking_number": None, "warehouse": "LA"},
        {"sku_id": 1, "quantity": 1, "exit_type": "loss", "tracking_number": "forbidden", "warehouse": "LA"},
        {"sku_id": 1, "quantity": 0, "exit_type": "loss", "tracking_number": None, "warehouse": "LA"},
        {"sku_id": 1, "quantity": 1, "exit_type": "other", "tracking_number": None, "warehouse": "LA"},
    ],
)
def test_outbound_schema_rejects_invalid_combinations(
    client: TestClient,
    auth_headers: dict[str, str],
    payload: dict[str, object],
) -> None:
    response = client.post("/inventory/orders/outbound", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert "input" not in response.text
    assert "tracking_number" not in response.text or "loc" in response.text


@pytest.mark.parametrize("field,value", [("warehouse", "NYC"), ("category", "food")])
def test_product_enum_validation(
    client: TestClient,
    auth_headers: dict[str, str],
    product_payload: dict[str, object],
    field: str,
    value: str,
) -> None:
    response = client.post(
        "/inventory/products",
        json={**product_payload, field: value},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert value not in response.text


def test_schema_has_no_stored_stock_or_user_table(engine: Engine) -> None:
    inspector = inspect(engine)
    assert "users" not in inspector.get_table_names()
    assert "current_stock" not in {column["name"] for column in inspector.get_columns("skus")}


def _base_sku() -> SKU:
    return SKU(
        name="Constraint Test",
        sku="CONSTRAINT-1",
        client_name="TrackFlow Test",
        category="fashion",
        warehouse="LA",
    )


def test_database_enforces_quantity_tracking_and_foreign_keys(engine: Engine) -> None:
    with Session(engine) as session:
        sku = _base_sku()
        session.add(sku)
        session.commit()
        session.refresh(sku)
        assert sku.id is not None

        invalid_rows = [
            StockEntry(
                sku_id=sku.id,
                quantity=0,
                reference="BAD-QTY",
                warehouse="LA",
                user_uuid="11111111-1111-4111-8111-111111111111",
            ),
            StockEntry(
                sku_id=9999,
                quantity=1,
                reference="BAD-FK",
                warehouse="LA",
                user_uuid="11111111-1111-4111-8111-111111111111",
            ),
            StockEntry(
                sku_id=sku.id,
                quantity=1,
                reference="BAD-WAREHOUSE",
                warehouse="ZGZ",
                user_uuid="11111111-1111-4111-8111-111111111111",
            ),
            StockExit(
                sku_id=sku.id,
                quantity=1,
                exit_type="dispatch",
                tracking_number=None,
                warehouse="LA",
                user_uuid="11111111-1111-4111-8111-111111111111",
            ),
        ]
        for row in invalid_rows:
            session.add(row)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()


def test_database_enforces_unique_sku_warehouse(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(_base_sku())
        session.commit()
        session.add(_base_sku())
        with pytest.raises(IntegrityError):
            session.commit()


def test_database_accepts_valid_loss_and_dispatch_constraints(engine: Engine) -> None:
    with Session(engine) as session:
        sku = _base_sku()
        session.add(sku)
        session.commit()
        session.refresh(sku)
        assert sku.id is not None
        session.add_all(
            [
                StockExit(
                    sku_id=sku.id,
                    quantity=1,
                    exit_type="dispatch",
                    tracking_number="TRACK-1",
                    warehouse="LA",
                    created_at=datetime.now(UTC),
                    user_uuid="11111111-1111-4111-8111-111111111111",
                ),
                StockExit(
                    sku_id=sku.id,
                    quantity=1,
                    exit_type="loss",
                    tracking_number=None,
                    warehouse="LA",
                    created_at=datetime.now(UTC),
                    user_uuid="11111111-1111-4111-8111-111111111111",
                ),
            ]
        )
        session.commit()
