"""Transactional threshold-crossing behavior for authoritative stockout events."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from central_api.domains.inventory.models import StockExit, StockoutEvent
from central_api.domains.inventory.schemas import ExitType, StockExitCreate, Warehouse
from central_api.domains.inventory.service import InventoryError, InventoryService

ACTOR_UUID = "11111111-1111-4111-8111-111111111111"


def _event_count(engine: Engine) -> int:
    with Session(engine) as session:
        return int(session.scalar(sa_select(func.count()).select_from(StockoutEvent)) or 0)


def test_stockout_emits_only_on_downward_crossing_and_inbound_only_rearms(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    engine: Engine,
) -> None:
    sku_id = created_product["id"]
    assert client.patch(
        f"/inventory/products/{sku_id}",
        json={"min_stock_threshold": 5},
        headers=auth_headers,
    ).status_code == 200
    assert client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 10, "reference": "STOCKOUT-1", "warehouse": "LA"},
        headers=auth_headers,
    ).status_code == 201
    assert _event_count(engine) == 0

    first_crossing = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 5,
            "exit_type": "dispatch",
            "tracking_number": "STOCKOUT-X1",
            "warehouse": "LA",
        },
        headers=auth_headers,
    )
    assert first_crossing.status_code == 201
    assert _event_count(engine) == 1

    # Remaining below the threshold is not another crossing.
    assert client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 1,
            "exit_type": "loss",
            "tracking_number": None,
            "warehouse": "LA",
        },
        headers=auth_headers,
    ).status_code == 201
    assert _event_count(engine) == 1

    # Inbound itself emits nothing, but moving above the threshold rearms a future crossing.
    assert client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 4, "reference": "STOCKOUT-2", "warehouse": "LA"},
        headers=auth_headers,
    ).status_code == 201
    assert _event_count(engine) == 1
    assert client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 3,
            "exit_type": "dispatch",
            "tracking_number": "STOCKOUT-X2",
            "warehouse": "LA",
        },
        headers=auth_headers,
    ).status_code == 201
    assert _event_count(engine) == 2


def test_concurrent_outbounds_create_exactly_one_crossing_event(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    engine: Engine,
) -> None:
    sku_id = created_product["id"]
    assert isinstance(sku_id, int)
    client.patch(
        f"/inventory/products/{sku_id}",
        json={"min_stock_threshold": 5},
        headers=auth_headers,
    )
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 11, "reference": "STOCKOUT-RACE", "warehouse": "LA"},
        headers=auth_headers,
    )
    barrier = Barrier(2)

    def dispatch(index: int) -> None:
        with Session(engine) as session:
            barrier.wait()
            InventoryService(session).record_outbound(
                StockExitCreate(
                    sku_id=sku_id,
                    quantity=3,
                    exit_type=ExitType.DISPATCH,
                    tracking_number=f"STOCKOUT-RACE-{index}",
                    warehouse=Warehouse.LA,
                ),
                ACTOR_UUID,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(dispatch, (1, 2)))

    assert client.get(f"/inventory/products/{sku_id}", headers=auth_headers).json()["current_stock"] == 5
    assert _event_count(engine) == 1


def test_stockout_insert_failure_rolls_back_triggering_exit(
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sku_id = created_product["id"]
    assert isinstance(sku_id, int)
    client.patch(
        f"/inventory/products/{sku_id}",
        json={"min_stock_threshold": 5},
        headers=auth_headers,
    )
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 10, "reference": "ROLLBACK", "warehouse": "LA"},
        headers=auth_headers,
    )

    with Session(engine) as session:
        service = InventoryService(session)

        def fail_event(_event: StockoutEvent) -> None:
            raise OperationalError("INSERT", {}, RuntimeError("forced event failure"))

        monkeypatch.setattr(service.repository, "add_stockout_event", fail_event)
        with pytest.raises(InventoryError) as raised:
            service.record_outbound(
                StockExitCreate(
                    sku_id=sku_id,
                    quantity=5,
                    exit_type=ExitType.DISPATCH,
                    tracking_number="ROLLBACK-TRACK",
                    warehouse=Warehouse.LA,
                ),
                ACTOR_UUID,
            )
        assert raised.value.status_code == 503

    with Session(engine) as session:
        assert int(session.scalar(sa_select(func.count()).select_from(StockExit)) or 0) == 0
        assert int(session.scalar(sa_select(func.count()).select_from(StockoutEvent)) or 0) == 0
