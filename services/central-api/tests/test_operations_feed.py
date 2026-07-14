"""Live operations feed + database-size guard: stock integrity, single-writer, safety."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.core.config import Settings
from central_api.domains.inventory.repository import InventoryRepository, entry_table, exit_table, sku_table
from central_api.domains.operations.control import feed_enabled, set_feed_enabled
from scripts import db_size_guard, operations_feed

SERVICE_UUID = "11111111-1111-4111-8111-111111111111"


def _feed_settings(settings: Settings, **overrides: object) -> Settings:
    base = {"operations_feed_batch_min": 3, "operations_feed_batch_max": 6, "operations_feed_backfill_days": 4}
    base.update(overrides)
    return settings.model_copy(update=base)


def _all_stock_nonnegative(session: Session) -> bool:
    repo = InventoryRepository(session)
    return all(
        repo.current_stock(sku_id, warehouse) >= 0
        for sku_id, warehouse in operations_feed._list_skus(session)
    )


# --- Stock integrity ----------------------------------------------------------------------


def test_backfill_populates_recent_ledger_without_negative_stock(engine: Engine, settings: Settings) -> None:
    with Session(engine) as session:
        operations_feed.ensure_baseline(session, SERVICE_UUID)
        written = operations_feed.backfill_history(session, SERVICE_UUID, days=5)
        assert written > 0
        assert operations_feed._recent_movement_count(session, 5) > 0
        assert _all_stock_nonnegative(session)


def test_sustained_ticks_never_drive_stock_negative(engine: Engine, settings: Settings) -> None:
    feed_settings = _feed_settings(settings)
    with Session(engine) as session:
        operations_feed.ensure_baseline(session, SERVICE_UUID)
        for _ in range(80):
            operations_feed.run_tick(session, SERVICE_UUID, feed_settings)
            assert _all_stock_nonnegative(session), "a tick drove computed stock negative"
        entries = int(session.scalar(sa_select(func.count()).select_from(entry_table)) or 0)
        exits = int(session.scalar(sa_select(func.count()).select_from(exit_table)) or 0)
        assert entries + exits > 0


def test_run_tick_without_skus_is_a_noop(engine: Engine, settings: Settings) -> None:
    with Session(engine) as session:
        assert operations_feed._list_skus(session) == []
        assert operations_feed.run_tick(session, SERVICE_UUID, _feed_settings(settings)) == 0


# --- Single-writer guarantee --------------------------------------------------------------


def test_advisory_lock_admits_only_one_writer(engine: Engine) -> None:
    key = 999_000_111
    first = engine.connect()
    second = engine.connect()
    try:
        assert operations_feed.acquire_singleton_lock(first, key) is True
        # A second connection cannot acquire the same key while the first holds it.
        assert operations_feed.acquire_singleton_lock(second, key) is False
    finally:
        first.close()  # closing the session releases its advisory locks
        second.close()


# --- Runtime kill switch ------------------------------------------------------------------


def test_kill_switch_round_trips(engine: Engine) -> None:
    with Session(engine) as session:
        assert feed_enabled(session) is True
        set_feed_enabled(session, enabled=False, note="paused for test")
    with Session(engine) as session:
        assert feed_enabled(session) is False
        set_feed_enabled(session, enabled=True, note="resumed")
    with Session(engine) as session:
        assert feed_enabled(session) is True


# --- Honest diagnostics + no PII ----------------------------------------------------------


def test_over_request_emits_real_dispatch_rejection(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    enabled = settings.model_copy(update={"telemetry_enabled": True, "app_env": "test"})
    monkeypatch.setattr("central_api.domains.telemetry.recorder.get_settings", lambda: enabled)
    operations_feed.record_dispatch_rejection(warehouse="LA", reason_code="INSUFFICIENT_STOCK", quantity=99)

    from sqlmodel import select as sqlmodel_select

    from central_api.domains.telemetry.models import TelemetryEvent

    with Session(engine) as session:
        rows = list(session.exec(sqlmodel_select(TelemetryEvent)).all())
    assert len(rows) == 1
    assert rows[0].event == "inventory.dispatch.rejected"
    assert rows[0].reason_code == "INSUFFICIENT_STOCK"
    # Allowlist holds: no free-text or PII keys ever reach the store.
    assert set(rows[0].properties) <= {"warehouse", "reason_code", "quantity"}


def test_feed_logs_carry_no_pii(engine: Engine, settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO), Session(engine) as session:
        operations_feed.ensure_baseline(session, SERVICE_UUID)
        operations_feed.backfill_history(session, SERVICE_UUID, days=2)
        operations_feed.run_tick(session, SERVICE_UUID, _feed_settings(settings))
    blob = "\n".join(record.getMessage() for record in caplog.records)
    assert "@" not in blob  # no emails
    assert SERVICE_UUID not in blob  # opaque actor id never logged


# --- Database-size guard ------------------------------------------------------------------


def test_database_size_is_measurable(engine: Engine) -> None:
    with Session(engine) as session:
        assert db_size_guard.database_size_mb(session) > 0


def test_guard_under_soft_limit_takes_no_action(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db_size_guard, "get_settings", lambda: _feed_settings(settings))
    monkeypatch.setattr(db_size_guard, "database_size_mb", lambda _session: 10.0)
    reset_called = {"value": False}
    monkeypatch.setattr(db_size_guard, "reset_ledger", lambda *a, **k: reset_called.__setitem__("value", True))
    db_size_guard.guard_once()
    assert reset_called["value"] is False


def test_guard_at_hard_limit_resets_and_reenables(
    engine: Engine, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed_settings = _feed_settings(settings, operations_feed_user_uuid=SERVICE_UUID)
    monkeypatch.setattr(db_size_guard, "get_settings", lambda: feed_settings)
    monkeypatch.setattr(db_size_guard, "database_size_mb", lambda _session: 460.0)
    with Session(engine) as session:
        set_feed_enabled(session, enabled=True, note="pre-test")

    db_size_guard.guard_once()

    with Session(engine) as session:
        # Reset paused then re-enabled the feed, and rebuilt a consistent, populated ledger.
        assert feed_enabled(session) is True
        assert int(session.scalar(sa_select(func.count()).select_from(sku_table)) or 0) > 0
        assert int(session.scalar(sa_select(func.count()).select_from(entry_table)) or 0) > 0
        assert _all_stock_nonnegative(session)
