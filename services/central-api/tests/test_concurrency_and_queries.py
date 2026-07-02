"""Transaction-race and aggregate-query regression tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.domains.inventory.schemas import ExitType, StockExitCreate, Warehouse
from central_api.domains.inventory.service import InventoryError, InventoryService


def test_concurrent_outbound_requests_cannot_make_stock_negative(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    assert isinstance(created_product["id"], int)
    sku_id = created_product["id"]
    inbound = client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 10, "reference": "RACE-STOCK", "warehouse": "LA"},
        headers=auth_headers,
    )
    assert inbound.status_code == 201
    barrier = Barrier(2)

    def attempt(index: int) -> int:
        with Session(engine) as session:
            service = InventoryService(session)
            barrier.wait()
            try:
                service.record_outbound(
                    StockExitCreate(
                        sku_id=sku_id,
                        quantity=7,
                        exit_type=ExitType.DISPATCH,
                        tracking_number=f"RACE-{index}",
                        warehouse=Warehouse.LA,
                    ),
                    "11111111-1111-4111-8111-111111111111",
                )
            except InventoryError as exc:
                return exc.status_code
            return 201

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(attempt, (1, 2)))

    assert outcomes == [201, 400]
    assert client.get(f"/inventory/products/{sku_id}", headers=auth_headers).json()["current_stock"] == 3


def test_product_and_movement_lists_do_not_use_n_plus_one_queries(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    for index in range(3):
        assert (
            client.post(
                "/inventory/orders/inbound",
                json={
                    "sku_id": created_product["id"],
                    "quantity": index + 1,
                    "reference": f"QUERY-{index}",
                    "warehouse": "LA",
                },
                headers=auth_headers,
            ).status_code
            == 201
        )

    statements: list[str] = []

    def count_query(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_query)
    try:
        assert client.get("/inventory/products", headers=auth_headers).status_code == 200
        product_queries = len(statements)
        statements.clear()
        assert client.get("/inventory/orders", headers=auth_headers).status_code == 200
        movement_queries = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

    # Each list uses one bounded data query and one total-count query regardless of rows.
    assert product_queries == 2
    assert movement_queries == 2
