"""Guards that keep the materialized balance trustworthy across deploys and prunes.

The interesting failure is not a single wrong number: it is that pruning destroys
the evidence needed to detect one. These prove the checkpoint chain keeps the
balance derivable, and that the pruner refuses to run when it is not.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.core.config import Settings
from central_api.domains.inventory.balances import (
    LedgerCheckpointError,
    checkpoint_watermark,
    reconcile_stock_balances,
    verify_stock_balances,
    write_ledger_checkpoint,
)
from scripts.prune_movement_ledger import BalancesDrifted, prune_once

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _no_sleep(_seconds: float) -> None:
    """Tests must not pay the inter-batch pacing delay."""


def _stock(client: TestClient, headers: dict[str, str], sku_id: object) -> int:
    return int(client.get(f"/inventory/products/{sku_id}", headers=headers).json()["current_stock"])


def _age_all_movements(engine: Engine, *, days: int) -> None:
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


def _seed_movements(client: TestClient, headers: dict[str, str], sku_id: object) -> None:
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 100, "reference": "GUARD-IN", "warehouse": "LA"},
        headers=headers,
    )
    client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": sku_id,
            "quantity": 30,
            "exit_type": "dispatch",
            "tracking_number": "GUARD-OUT",
            "warehouse": "LA",
        },
        headers=headers,
    )


def test_balance_survives_pruning_because_the_checkpoint_carries_it(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    settings: Settings,
) -> None:
    """The whole point of the checkpoint: after the movements that produced a
    balance are deleted, the balance must still verify and still be correct."""
    sku_id = created_product["id"]
    _seed_movements(client, auth_headers, sku_id)
    assert _stock(client, auth_headers, sku_id) == 70

    _age_all_movements(engine, days=90)
    prune_once(
        now=NOW,
        settings=settings.model_copy(update={"movement_retention_days": 30}),
        batch_size=100,
        sleep_seconds=0.0,
        sleep=_no_sleep,
    )

    with Session(engine) as session:
        # Every movement is gone, yet the balance is intact and verifies.
        assert int(session.scalar(text("SELECT count(*) FROM stock_entries")) or 0) == 0
        assert int(session.scalar(text("SELECT count(*) FROM stock_exits")) or 0) == 0
        assert checkpoint_watermark(session) == NOW - timedelta(days=30)
        assert verify_stock_balances(session) == []
    assert _stock(client, auth_headers, sku_id) == 70


def test_successive_prunes_chain_their_checkpoints(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    settings: Settings,
) -> None:
    """A second prune must build on the first checkpoint, not re-derive from a
    ledger whose earlier half no longer exists."""
    sku_id = created_product["id"]
    _seed_movements(client, auth_headers, sku_id)
    _age_all_movements(engine, days=90)
    tuned = settings.model_copy(update={"movement_retention_days": 30})

    prune_once(now=NOW, settings=tuned, batch_size=100, sleep_seconds=0.0, sleep=_no_sleep)

    # New activity after the first prune, then a later prune that absorbs it.
    client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": 10, "reference": "CHAIN-IN", "warehouse": "LA"},
        headers=auth_headers,
    )
    assert _stock(client, auth_headers, sku_id) == 80
    # Old enough for the later prune to absorb, but still after the first
    # checkpoint -- a movement below an existing watermark is by definition
    # already folded into its base.
    _age_all_movements(engine, days=10)

    later = NOW + timedelta(days=31)
    prune_once(now=later, settings=tuned, batch_size=100, sleep_seconds=0.0, sleep=_no_sleep)

    with Session(engine) as session:
        assert checkpoint_watermark(session) == later - timedelta(days=30)
        assert verify_stock_balances(session) == []
    assert _stock(client, auth_headers, sku_id) == 80


def test_pruner_refuses_while_balances_are_drifted(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    settings: Settings,
) -> None:
    """Deleting movements destroys the evidence needed to diagnose drift, so the
    pruner must stop rather than bury it."""
    sku_id = created_product["id"]
    _seed_movements(client, auth_headers, sku_id)
    _age_all_movements(engine, days=90)

    with Session(engine) as session:
        session.execute(
            text("UPDATE stock_balances SET quantity = quantity + 500 WHERE sku_id = :id"),
            {"id": sku_id},
        )
        session.commit()

    with pytest.raises(BalancesDrifted):
        prune_once(
            now=NOW,
            settings=settings.model_copy(update={"movement_retention_days": 30}),
            batch_size=100,
            sleep_seconds=0.0,
            sleep=_no_sleep,
        )

    with Session(engine) as session:
        # Nothing deleted and no checkpoint written: the run is fully recoverable.
        assert int(session.scalar(text("SELECT count(*) FROM stock_entries")) or 0) >= 1
        assert checkpoint_watermark(session) is None


def test_reconcile_repairs_deploy_rollover_drift(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    """Reproduces the production symptom: movements written by an old image that
    never updated the balance, leaving stored higher than the ledger."""
    sku_id = created_product["id"]
    _seed_movements(client, auth_headers, sku_id)

    with Session(engine) as session:
        # An exit that bypassed the incremental path, exactly as the previous
        # image's code would have written it.
        session.execute(
            text(
                "INSERT INTO stock_exits "
                "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                "VALUES (:sku, 25, 'dispatch', 'ROLLOVER', 'LA', now(), :user)"
            ),
            {"sku": sku_id, "user": "11111111-1111-4111-8111-111111111111"},
        )
        session.commit()

    with Session(engine) as session:
        drifted = verify_stock_balances(session)
        assert len(drifted) == 1
        # Stored over-states stock, which is what authorises impossible dispatches.
        assert drifted[0].delta == -25

    with Session(engine) as session:
        corrected = reconcile_stock_balances(session)
        session.commit()
    assert len(corrected) == 1

    assert _stock(client, auth_headers, sku_id) == 45
    with Session(engine) as session:
        assert verify_stock_balances(session) == []


def test_split_checkpoint_refuses_rather_than_guessing_a_base(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
    product_payload: dict[str, object],
) -> None:
    """An interrupted or hand-edited checkpoint has no single correct base."""
    sku_id = created_product["id"]
    _seed_movements(client, auth_headers, sku_id)
    second = client.post(
        "/inventory/products",
        json={**product_payload, "sku": "CLT-SNK-W-43"},
        headers=auth_headers,
    )
    assert second.status_code == 201

    with Session(engine) as session:
        write_ledger_checkpoint(session, NOW - timedelta(days=30))
        # One row disagreeing is enough: there is no single base to derive from.
        session.execute(
            text(
                "UPDATE stock_ledger_checkpoints SET checkpoint_at = :other WHERE sku_id = :sku"
            ),
            {"other": NOW - timedelta(days=10), "sku": second.json()["id"]},
        )
        session.commit()

    with Session(engine) as session, pytest.raises(LedgerCheckpointError):
        verify_stock_balances(session)


def test_checkpoint_refuses_to_move_backwards(
    engine: Engine,
    client: TestClient,
    auth_headers: dict[str, str],
    created_product: dict[str, object],
) -> None:
    """Re-checkpointing at an earlier instant would double-count movements
    already folded into the existing base."""
    _seed_movements(client, auth_headers, created_product["id"])
    with Session(engine) as session:
        write_ledger_checkpoint(session, NOW - timedelta(days=30))
        session.commit()
    with Session(engine) as session, pytest.raises(LedgerCheckpointError):
        write_ledger_checkpoint(session, NOW - timedelta(days=60))
