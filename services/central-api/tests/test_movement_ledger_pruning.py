"""Retention proofs for the movement ledger and the events referencing it.

The foreign-key ordering test is the important one: `inventory_discrepancies`
and `stockout_events` hold ON DELETE RESTRICT keys into `stock_exits`, so getting
the order or the child predicate wrong makes the parent delete raise in
production rather than fail a test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.core.config import Settings
from scripts import prune_movement_ledger
from scripts.prune_movement_ledger import (
    RetentionWindowTooShort,
    prune_once,
    retention_cutoff,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _no_sleep(_seconds: float) -> None:
    """Tests must not pay the inter-batch pacing delay."""


def _age_all_movements(engine: Engine, *, days: int) -> None:
    """Backdate the whole ledger so retention has something to act on."""
    with Session(engine) as session:
        moved = NOW - timedelta(days=days)
        for table, column in (
            ("stock_entries", "created_at"),
            ("stock_exits", "created_at"),
            ("stockout_events", "occurred_at"),
            ("inventory_discrepancies", "detected_at"),
        ):
            session.execute(text(f"UPDATE {table} SET {column} = :moved"), {"moved": moved})
        session.commit()


def _counts(engine: Engine) -> dict[str, int]:
    with Session(engine) as session:
        return {
            table: int(session.scalar(text(f"SELECT count(*) FROM {table}")) or 0)
            for table in (
                "stock_entries",
                "stock_exits",
                "stockout_events",
                "inventory_discrepancies",
            )
        }


def test_retention_refuses_a_window_inside_the_reporting_recompute_range() -> None:
    """Reporting recomputes a trailing 21 days; deleting inside it republishes
    silently wrong numbers, so the job must fail closed rather than run."""
    with pytest.raises(RetentionWindowTooShort):
        retention_cutoff(NOW, prune_movement_ledger.REPORTING_RECOMPUTE_DAYS)
    with pytest.raises(RetentionWindowTooShort):
        retention_cutoff(NOW, 14)

    assert retention_cutoff(NOW, 30) == NOW - timedelta(days=30)


def test_prune_removes_child_events_before_their_restricted_parents(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    settings: Settings,
) -> None:
    """A dispatch that produced both a stockout event and a discrepancy must be
    deletable. Wrong ordering raises ForeignKeyViolation instead."""
    sku_id = created_product["id"]
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 20, "reference": "PRUNE-IN", "warehouse": "LA"},
        headers=auth_headers,
    )
    client.patch(
        f"/inventory/products/{sku_id}",
        json={"min_stock_threshold": 15},
        headers=auth_headers,
    )
    outbound = client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 10,
            "exit_type": "dispatch",
            "tracking_number": "PRUNE-OUT",
            "warehouse": "LA",
        },
        headers=auth_headers,
    )
    assert outbound.status_code == 201
    exit_id = outbound.json()["id"]
    assert client.post(
        "/inventory/discrepancies",
        json={"stock_exit_id": exit_id, "quantity_delta": -1},
        headers=auth_headers,
    ).status_code in {200, 201}

    before = _counts(engine)
    assert before["stock_exits"] >= 1
    assert before["inventory_discrepancies"] >= 1
    assert before["stockout_events"] >= 1

    _age_all_movements(engine, days=90)
    deleted = prune_once(
        now=NOW,
        settings=settings.model_copy(update={"movement_retention_days": 30}),
        batch_size=100,
        sleep_seconds=0.0,
        sleep=_no_sleep,
    )

    assert _counts(engine) == {
        "stock_entries": 0,
        "stock_exits": 0,
        "stockout_events": 0,
        "inventory_discrepancies": 0,
    }
    assert deleted["inventory_discrepancies"] >= 1
    assert deleted["stockout_events"] >= 1
    assert deleted["stock_exits"] >= 1


def test_prune_retains_movements_inside_the_window(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    settings: Settings,
) -> None:
    sku_id = created_product["id"]
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 12, "reference": "KEEP-IN", "warehouse": "LA"},
        headers=auth_headers,
    )
    _age_all_movements(engine, days=5)

    deleted = prune_once(
        now=NOW,
        settings=settings.model_copy(update={"movement_retention_days": 30}),
        batch_size=100,
        sleep_seconds=0.0,
        sleep=_no_sleep,
    )

    assert deleted == {
        "inventory_discrepancies": 0,
        "stockout_events": 0,
        "stock_exits": 0,
        "stock_entries": 0,
    }
    assert _counts(engine)["stock_entries"] >= 1


def test_prune_stops_at_its_time_budget_without_orphaning_parents(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    settings: Settings,
) -> None:
    """An exhausted budget must stop before parents whose children remain, so a
    partial run is always resumable rather than leaving an impossible delete."""
    sku_id = created_product["id"]
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 9, "reference": "BUDGET-IN", "warehouse": "LA"},
        headers=auth_headers,
    )
    _age_all_movements(engine, days=90)

    ticks = iter([0.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    deleted = prune_once(
        now=NOW,
        settings=settings.model_copy(update={"movement_retention_days": 30}),
        batch_size=100,
        sleep_seconds=0.0,
        max_seconds=1.0,
        monotonic=lambda: next(ticks),
        sleep=_no_sleep,
    )

    # Budget expired on the first step, so nothing further was attempted.
    assert deleted == {"inventory_discrepancies": 0}
    assert _counts(engine)["stock_entries"] >= 1
