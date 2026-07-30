"""Reference and reconciliation proofs for durable hourly SQL rollups."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, inspect, text

from pipelines.business_performance import rollups
from pipelines.business_performance.queue import RunClaim, claim_next, enqueue_cli
from pipelines.business_performance.rollups import (
    ReconciliationResult,
    RollupValidationError,
    activate_reconciled_rollups,
    capture_rollup_window,
    compute_hourly_rollups,
    hourly_rollups_enabled,
    publish_hourly_rollups,
    reconcile_hourly_rollups,
    rollup_cutover_enabled,
)

WEEK = date(2026, 12, 28)
WEEK_START = datetime(2026, 12, 28, tzinfo=UTC)
CUTOFF = datetime(2027, 1, 4, tzinfo=UTC)


def _seed_dimensions(engine: Engine) -> tuple[UUID, UUID, int]:
    active_client = uuid4()
    inactive_client = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clients (id, display_name) VALUES "
                "(:active, 'Rollup Active'), (:inactive, 'Rollup Inactive')"
            ),
            {"active": active_client, "inactive": inactive_client},
        )
        active_sku = int(
            connection.scalar(
                text(
                    "INSERT INTO skus "
                    "(name, sku, client_id, min_stock_threshold, category, warehouse) "
                    "VALUES ('Active SKU', 'ROLLUP-A', :client_id, 1, 'fashion', 'LA') RETURNING id"
                ),
                {"client_id": active_client},
            )
        )
        connection.execute(
            text(
                "INSERT INTO skus "
                "(name, sku, client_id, min_stock_threshold, category, warehouse) "
                "VALUES ('Inactive SKU', 'ROLLUP-Z', :client_id, 0, 'fashion', 'ZGZ')"
            ),
            {"client_id": inactive_client},
        )
    return active_client, inactive_client, active_sku


def _insert_activity(engine: Engine, client_id: UUID, sku_id: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO stock_entries "
                "(sku_id, quantity, reference, warehouse, created_at, user_uuid) VALUES "
                "(:sku, 5, 'rollup-entry-1', 'LA', :at, :user), "
                "(:sku, 7, 'rollup-entry-2', 'LA', :next_hour, :user)"
            ),
            {
                "sku": sku_id,
                "at": WEEK_START,
                "next_hour": WEEK_START + timedelta(hours=1),
                "user": str(uuid4()),
            },
        )
        dispatch_id = int(
            connection.scalar(
                text(
                    "INSERT INTO stock_exits "
                    "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                    "VALUES (:sku, 3, 'dispatch', 'ROLLUP-D', 'LA', :at, :user) RETURNING id"
                ),
                {
                    "sku": sku_id,
                    "at": WEEK_START + timedelta(hours=1),
                    "user": str(uuid4()),
                },
            )
        )
        connection.execute(
            text(
                "INSERT INTO stock_exits "
                "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                "VALUES (:sku, 2, 'loss', NULL, 'LA', :at, :user)"
            ),
            {
                "sku": sku_id,
                "at": WEEK_START + timedelta(hours=1),
                "user": str(uuid4()),
            },
        )
        connection.execute(
            text(
                "INSERT INTO stockout_events "
                "(sku_id, warehouse, client_id, threshold_at_event, stock_after, stock_exit_id, occurred_at) "
                "VALUES (:sku, 'LA', :client, 1, 0, :exit, :at)"
            ),
            {
                "sku": sku_id,
                "client": client_id,
                "exit": dispatch_id,
                "at": WEEK_START + timedelta(hours=1),
            },
        )
        connection.execute(
            text(
                "INSERT INTO inventory_discrepancies "
                "(stock_exit_id, sku_id, warehouse, client_id, quantity_delta, source, detected_at) "
                "VALUES (:exit, :sku, 'LA', :client, 1, 'feed', :at)"
            ),
            {
                "exit": dispatch_id,
                "sku": sku_id,
                "client": client_id,
                "at": WEEK_START + timedelta(hours=1),
            },
        )


def _claim(engine: Engine) -> RunClaim:
    enqueue_cli(
        engine,
        requested_week_start=WEEK,
        now=WEEK_START - timedelta(seconds=1),
    )
    claim = claim_next(engine, now=CUTOFF)
    assert claim is not None
    return claim


def test_flag_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPORTING_HOURLY_ROLLUPS_ENABLED", raising=False)
    assert hourly_rollups_enabled() is False
    monkeypatch.setenv("REPORTING_HOURLY_ROLLUPS_ENABLED", "true")
    assert hourly_rollups_enabled() is True
    monkeypatch.delenv("REPORTING_ROLLUP_CUTOVER_ENABLED", raising=False)
    assert rollup_cutover_enabled() is False
    monkeypatch.setenv("REPORTING_ROLLUP_CUTOVER_ENABLED", "true")
    assert rollup_cutover_enabled() is True


def test_empty_default_window_publishes_cursor_without_rows(
    pipeline_engine: Engine,
) -> None:
    enqueue_cli(pipeline_engine, now=CUTOFF - timedelta(seconds=1))
    claim = claim_next(pipeline_engine, now=CUTOFF)
    assert claim is not None
    window = capture_rollup_window(pipeline_engine, claim, now=CUTOFF)
    assert window.start == CUTOFF - timedelta(hours=72)
    assert window.rows_scanned == 0
    rows = compute_hourly_rollups(pipeline_engine, window)
    assert rows == []
    assert (
        publish_hourly_rollups(
            pipeline_engine,
            claim,
            window,
            rows,
            now=CUTOFF,
        )
        == 0
    )
    with pipeline_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT last_cutoff_at FROM reporting.rollup_state WHERE id = 1")
            )
            == CUTOFF
        )


def test_reset_boundary_fails_closed(
    pipeline_engine: Engine,
) -> None:
    enqueue_cli(pipeline_engine, now=CUTOFF - timedelta(seconds=1))
    claim = claim_next(pipeline_engine, now=CUTOFF)
    assert claim is not None
    with pipeline_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE reporting.source_ledger_state SET last_reset_at = :cutoff "
                "WHERE id = 1"
            ),
            {"cutoff": CUTOFF},
        )
    with pytest.raises(RollupValidationError, match="no completed"):
        capture_rollup_window(pipeline_engine, claim, now=CUTOFF)


def test_rollup_time_validation_and_cli_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(RollupValidationError, match="timezone-aware"):
        rollups._floor_hour(datetime(2026, 7, 1))
    with pytest.raises(RollupValidationError, match="no completed"):
        reconcile_hourly_rollups(
            SimpleNamespace(),  # type: ignore[arg-type]
            start=CUTOFF,
            cutoff=CUTOFF,
        )
    with pytest.raises(Exception, match="UTC offset"):
        rollups._parse_instant("2026-07-01T00:00:00")
    with pytest.raises(Exception, match="ISO-8601"):
        rollups._parse_instant("not-a-time")

    fake_engine = SimpleNamespace(dispose=lambda: None)
    monkeypatch.setattr(rollups, "engine_from_environment", lambda: fake_engine)
    monkeypatch.setattr(
        rollups,
        "reconcile_hourly_rollups",
        lambda *_args, **_kwargs: ReconciliationResult(4, ()),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "rollups",
            "--start",
            "2026-07-01T00:00:00Z",
            "--cutoff",
            "2026-07-02T00:00:00Z",
        ],
    )
    rollups.main()
    assert capsys.readouterr().out == (
        "reporting_rollup_reconciliation=passed dimensions=4\n"
    )

    mismatch = rollups.ReconciliationMismatch(
        WEEK,
        "LA",
        uuid4(),
        ("inbound_units",),
    )
    monkeypatch.setattr(
        rollups,
        "reconcile_hourly_rollups",
        lambda *_args, **_kwargs: ReconciliationResult(4, (mismatch,)),
    )
    with pytest.raises(SystemExit) as exit_info:
        rollups.main()
    assert exit_info.value.code == 1
    assert capsys.readouterr().out == (
        "reporting_rollup_reconciliation=failed mismatches=1\n"
    )


def test_reference_rollup_is_dense_separates_dispatch_and_loss_and_reconciles(
    pipeline_engine: Engine,
) -> None:
    active_client, inactive_client, sku_id = _seed_dimensions(pipeline_engine)
    _insert_activity(pipeline_engine, active_client, sku_id)
    claim = _claim(pipeline_engine)
    window = capture_rollup_window(pipeline_engine, claim, now=CUTOFF)
    rows = compute_hourly_rollups(pipeline_engine, window)

    assert window.start == WEEK_START
    assert window.end == CUTOFF
    assert window.source_cutoff_at == CUTOFF
    assert window.rows_scanned == 6
    assert len(rows) == 7 * 24 * 2

    first_hour = next(
        row
        for row in rows
        if row.bucket_start == WEEK_START and row.client_id == active_client
    )
    assert (first_hour.inbound_movement_count, first_hour.inbound_units) == (1, 5)
    second_hour = next(
        row
        for row in rows
        if row.bucket_start == WEEK_START + timedelta(hours=1)
        and row.client_id == active_client
    )
    assert (
        second_hour.inbound_movement_count,
        second_hour.inbound_units,
        second_hour.dispatch_order_count,
        second_hour.dispatch_units,
        second_hour.loss_movement_count,
        second_hour.loss_units,
        second_hour.stockout_count,
        second_hour.discrepancy_count,
    ) == (1, 7, 1, 3, 1, 2, 1, 1)
    zero_dimension = next(
        row
        for row in rows
        if row.bucket_start == WEEK_START and row.client_id == inactive_client
    )
    assert (
        zero_dimension.dispatch_order_count,
        zero_dimension.discrepancy_count,
    ) == (0, 0)

    written = publish_hourly_rollups(
        pipeline_engine,
        claim,
        window,
        rows,
        now=CUTOFF,
    )
    assert written == len(rows)
    result = reconcile_hourly_rollups(
        pipeline_engine,
        start=WEEK_START,
        cutoff=CUTOFF,
    )
    assert result.exact is True
    assert result.checked_dimensions == 2
    assert "discrepancy_rate" not in {
        column["name"]
        for column in inspect(pipeline_engine).get_columns(
            "hourly_activity_rollups",
            schema="reporting",
        )
    }

    # The same fixed cutoff is idempotent: identical keys are updated, never duplicated.
    assert publish_hourly_rollups(
        pipeline_engine,
        claim,
        window,
        rows,
        now=CUTOFF + timedelta(seconds=1),
    ) == len(rows)
    with pipeline_engine.connect() as connection:
        assert int(
            connection.scalar(
                text("SELECT count(*) FROM reporting.hourly_activity_rollups")
            )
        ) == len(rows)


def test_activation_publishes_complete_week_and_preserves_last_verified_on_mismatch(
    pipeline_engine: Engine,
) -> None:
    active_client, _inactive_client, sku_id = _seed_dimensions(pipeline_engine)
    _insert_activity(pipeline_engine, active_client, sku_id)
    claim = _claim(pipeline_engine)
    window = capture_rollup_window(pipeline_engine, claim, now=CUTOFF)
    rows = compute_hourly_rollups(pipeline_engine, window)
    publish_hourly_rollups(pipeline_engine, claim, window, rows, now=CUTOFF)

    activated_at = CUTOFF + timedelta(seconds=2)
    activated = activate_reconciled_rollups(
        pipeline_engine,
        claim,
        window,
        now=activated_at,
    )
    assert activated.reconciliation.exact is True
    assert activated.weekly_rows_written == 2
    with pipeline_engine.connect() as connection:
        active = connection.execute(
            text(
                "SELECT active_pipeline_version, active_cutoff_at, active_published_at "
                "FROM reporting.rollup_state WHERE id = 1"
            )
        ).one()
        weekly = connection.execute(
            text(
                "SELECT inbound_units_count, outbound_orders_count, "
                "stockout_events_count, discrepancy_events_count "
                "FROM reporting.weekly_warehouse_client_performance "
                "WHERE week_start = :week AND client_id = :client"
            ),
            {"week": WEEK, "client": active_client},
        ).one()
    assert active == ("engagement-6-phase-6.3", CUTOFF, activated_at)
    assert weekly == (12, 1, 1, 1)

    with pipeline_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO stock_entries "
                "(sku_id, quantity, reference, warehouse, created_at, user_uuid) "
                "VALUES (:sku, 9, 'post-activation-mismatch', 'LA', :at, :user)"
            ),
            {
                "sku": sku_id,
                "at": CUTOFF - timedelta(hours=2),
                "user": str(uuid4()),
            },
        )
    candidate = compute_hourly_rollups(pipeline_engine, window)
    candidate[0] = replace(
        candidate[0],
        inbound_units=candidate[0].inbound_units + 1,
    )
    with pytest.raises(RollupValidationError, match="reconciliation failed"):
        activate_reconciled_rollups(
            pipeline_engine,
            claim,
            window,
            rows=candidate,
            now=activated_at + timedelta(minutes=1),
        )
    with pipeline_engine.connect() as connection:
        unchanged = connection.execute(
            text(
                "SELECT active_pipeline_version, active_cutoff_at, active_published_at "
                "FROM reporting.rollup_state WHERE id = 1"
            )
        ).one()
        preserved_units = int(
            connection.scalar(
                text(
                    "SELECT sum(inbound_units) FROM reporting.hourly_activity_rollups "
                    "WHERE client_id = :client"
                ),
                {"client": active_client},
            )
        )
    assert unchanged == active
    assert preserved_units == 12


def test_fixed_cutoff_snapshot_excludes_mid_run_insert_then_trailing_recompute_repairs(
    pipeline_engine: Engine,
) -> None:
    client_id, _inactive_client, sku_id = _seed_dimensions(pipeline_engine)
    claim = _claim(pipeline_engine)
    window = capture_rollup_window(pipeline_engine, claim, now=CUTOFF)
    rows_before_arrival = compute_hourly_rollups(pipeline_engine, window)

    with pipeline_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO stock_entries "
                "(sku_id, quantity, reference, warehouse, created_at, user_uuid) "
                "VALUES (:sku, 9, 'late-arrival', 'LA', :at, :user)"
            ),
            {
                "sku": sku_id,
                "at": CUTOFF - timedelta(hours=2),
                "user": str(uuid4()),
            },
        )
    publish_hourly_rollups(
        pipeline_engine,
        claim,
        window,
        rows_before_arrival,
        now=CUTOFF,
    )
    first_reconciliation = reconcile_hourly_rollups(
        pipeline_engine,
        start=WEEK_START,
        cutoff=CUTOFF,
        mark_reconciled=False,
    )
    assert first_reconciliation.exact is False
    assert first_reconciliation.mismatches[0].client_id == client_id
    assert "inbound_units" in first_reconciliation.mismatches[0].metrics

    repaired_rows = compute_hourly_rollups(pipeline_engine, window)
    publish_hourly_rollups(
        pipeline_engine,
        claim,
        window,
        repaired_rows,
        now=CUTOFF + timedelta(seconds=1),
    )
    assert reconcile_hourly_rollups(
        pipeline_engine,
        start=WEEK_START,
        cutoff=CUTOFF,
    ).exact

    with pipeline_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE reporting.rollup_state SET last_cutoff_at = :cutoff WHERE id = 1"
            ),
            {"cutoff": CUTOFF},
        )
    default_claim_id = enqueue_cli(
        pipeline_engine,
        now=CUTOFF + timedelta(hours=12) - timedelta(seconds=1),
    )
    assert default_claim_id is not None
    # Release the first claim so the default request can be claimed.
    with pipeline_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE reporting.pipeline_runs SET status = 'succeeded', claim_token = NULL "
                "WHERE id = :id"
            ),
            {"id": claim.run_id},
        )
    default_claim = claim_next(pipeline_engine, now=CUTOFF + timedelta(hours=12))
    assert default_claim is not None
    trailing = capture_rollup_window(
        pipeline_engine,
        default_claim,
        now=CUTOFF + timedelta(hours=12),
    )
    assert trailing.start == CUTOFF - timedelta(hours=60)
    assert trailing.end == CUTOFF + timedelta(hours=12)


def test_reconciliation_blocks_discrepancies_without_dispatch_denominator(
    pipeline_engine: Engine,
) -> None:
    client_id, _inactive_client, sku_id = _seed_dimensions(pipeline_engine)
    with pipeline_engine.begin() as connection:
        loss_id = int(
            connection.scalar(
                text(
                    "INSERT INTO stock_exits "
                    "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                    "VALUES (:sku, 1, 'loss', NULL, 'LA', :at, :user) RETURNING id"
                ),
                {
                    "sku": sku_id,
                    "at": WEEK_START,
                    "user": str(uuid4()),
                },
            )
        )
        connection.execute(
            text(
                "INSERT INTO inventory_discrepancies "
                "(stock_exit_id, sku_id, warehouse, client_id, quantity_delta, source, detected_at) "
                "VALUES (:exit, :sku, 'LA', :client, 1, 'feed', :at)"
            ),
            {
                "exit": loss_id,
                "sku": sku_id,
                "client": client_id,
                "at": WEEK_START,
            },
        )
    claim = _claim(pipeline_engine)
    window = capture_rollup_window(pipeline_engine, claim, now=CUTOFF)
    publish_hourly_rollups(
        pipeline_engine,
        claim,
        window,
        compute_hourly_rollups(pipeline_engine, window),
        now=CUTOFF,
    )
    result = reconcile_hourly_rollups(
        pipeline_engine,
        start=WEEK_START,
        cutoff=CUTOFF,
        mark_reconciled=False,
    )
    assert result.exact is False
    assert "discrepancy_rate_denominator" in result.mismatches[0].metrics
