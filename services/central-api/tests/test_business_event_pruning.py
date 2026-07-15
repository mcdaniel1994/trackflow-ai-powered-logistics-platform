"""Business-event retention keeps recent source occurrences and prunes expired rows."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.core.config import Settings
from scripts import operations_feed, prune_business_events

SERVICE_UUID = "11111111-1111-4111-8111-111111111111"


def test_prune_business_events_keeps_the_retained_window(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 7, 15, 12, tzinfo=UTC)
    old = now - timedelta(weeks=27)
    recent = now - timedelta(weeks=2)
    with Session(engine) as session:
        operations_feed.ensure_baseline(session, SERVICE_UUID)
        sku_id, warehouse = operations_feed._list_skus(session)[0]
        client_id = session.execute(
            text("SELECT client_id FROM skus WHERE id = :sku_id"), {"sku_id": sku_id}
        ).scalar_one()
        exit_ids: list[int] = []
        for index, occurred_at in enumerate((old, recent), start=1):
            exit_id = session.execute(
                text(
                    "INSERT INTO stock_exits "
                    "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                    "VALUES (:sku_id, 1, 'dispatch', :tracking, :warehouse, :occurred_at, :user_uuid) "
                    "RETURNING id"
                ),
                {
                    "sku_id": sku_id,
                    "tracking": f"PRUNE-{index}",
                    "warehouse": warehouse,
                    "occurred_at": occurred_at,
                    "user_uuid": SERVICE_UUID,
                },
            ).scalar_one()
            exit_ids.append(int(exit_id))
            session.execute(
                text(
                    "INSERT INTO stockout_events "
                    "(sku_id, warehouse, client_id, threshold_at_event, stock_after, stock_exit_id, occurred_at) "
                    "VALUES (:sku_id, :warehouse, :client_id, 1, 0, :exit_id, :occurred_at)"
                ),
                {
                    "sku_id": sku_id,
                    "warehouse": warehouse,
                    "client_id": client_id,
                    "exit_id": exit_id,
                    "occurred_at": occurred_at,
                },
            )
            session.execute(
                text(
                    "INSERT INTO inventory_discrepancies "
                    "(stock_exit_id, sku_id, warehouse, client_id, quantity_delta, source, detected_at) "
                    "VALUES (:exit_id, :sku_id, :warehouse, :client_id, 1, 'feed', :occurred_at)"
                ),
                {
                    "exit_id": exit_id,
                    "sku_id": sku_id,
                    "warehouse": warehouse,
                    "client_id": client_id,
                    "occurred_at": occurred_at,
                },
            )
        session.commit()

    monkeypatch.setattr(prune_business_events, "get_engine", lambda: engine)
    monkeypatch.setattr(
        prune_business_events,
        "get_settings",
        lambda: settings.model_copy(update={"business_event_retention_weeks": 26}),
    )
    assert prune_business_events.prune_once(now=now) == {
        "inventory_discrepancies": 1,
        "stockout_events": 1,
    }
    with Session(engine) as session:
        assert session.execute(text("SELECT stock_exit_id FROM stockout_events")).scalar_one() == exit_ids[1]
        assert session.execute(text("SELECT stock_exit_id FROM inventory_discrepancies")).scalar_one() == exit_ids[1]
