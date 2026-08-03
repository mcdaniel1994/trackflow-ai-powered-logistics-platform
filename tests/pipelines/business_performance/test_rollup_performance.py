"""Opt-in production-volume budget proof for Engagement 6.2 rollups."""

from __future__ import annotations

import os
import resource
import sys
from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from pipelines.business_performance.queue import claim_next, enqueue_cli
from pipelines.business_performance.rollups import (
    RollupWindow,
    compute_hourly_rollups,
    publish_hourly_rollups,
    reconcile_hourly_rollups,
)

PROJECTED_SIX_MONTH_MOVEMENTS = 1_050_000
TOTAL_MOVEMENTS = PROJECTED_SIX_MONTH_MOVEMENTS * 2
OBSERVED_PRODUCTION_DENSE_ROWS = 113_064
WORKER_LIMIT_BYTES = 768 * 1024 * 1024


def _seed_projection(engine: Engine, *, start: datetime, end: datetime) -> None:
    client_ids = [uuid4() for _ in range(3)]
    client_id = client_ids[0]
    user_id = str(uuid4())
    total_hours = int((end - start).total_seconds() // 3600)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO clients (id, display_name) VALUES (:id, :display_name)"),
            [
                {"id": seeded_client, "display_name": f"Rollup Performance {index}"}
                for index, seeded_client in enumerate(client_ids, start=1)
            ],
        )
        sku_ids = connection.execute(
            text(
                "INSERT INTO skus "
                "(name, sku, client_id, min_stock_threshold, category, warehouse) VALUES "
                "('Performance LA', 'PERF-LA', :client, 1, 'fashion', 'LA'), "
                "('Performance ZGZ', 'PERF-ZGZ', :client, 1, 'fashion', 'ZGZ') "
                "RETURNING id, warehouse"
            ),
            {"client": client_id},
        ).all()
        sku_by_warehouse = {str(warehouse): int(sku_id) for sku_id, warehouse in sku_ids}
        for index, inactive_client in enumerate(client_ids[1:], start=2):
            connection.execute(
                text(
                    "INSERT INTO skus "
                    "(name, sku, client_id, min_stock_threshold, category, warehouse) VALUES "
                    "(:la_name, :la_sku, :client, 1, 'fashion', 'LA'), "
                    "(:zgz_name, :zgz_sku, :client, 1, 'fashion', 'ZGZ')"
                ),
                {
                    "la_name": f"Performance LA {index}",
                    "la_sku": f"PERF-LA-{index}",
                    "zgz_name": f"Performance ZGZ {index}",
                    "zgz_sku": f"PERF-ZGZ-{index}",
                    "client": inactive_client,
                },
            )
        per_source = TOTAL_MOVEMENTS // 2
        connection.execute(
            text(
                "INSERT INTO stock_entries "
                "(sku_id, quantity, reference, warehouse, created_at, user_uuid) "
                "SELECT CASE WHEN n % 2 = 0 THEN :la_sku ELSE :zgz_sku END, "
                "1 + (n % 9), 'perf-entry-' || n, "
                "CASE WHEN n % 2 = 0 THEN 'LA' ELSE 'ZGZ' END, "
                ":start + ((n % :hours) * interval '1 hour') + ((n % 3600) * interval '1 second'), "
                ":user_id FROM generate_series(1, :row_count) AS n"
            ),
            {
                "la_sku": sku_by_warehouse["LA"],
                "zgz_sku": sku_by_warehouse["ZGZ"],
                "start": start,
                "hours": total_hours,
                "user_id": user_id,
                "row_count": per_source,
            },
        )
        connection.execute(
            text(
                "INSERT INTO stock_exits "
                "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                "SELECT CASE WHEN n % 2 = 0 THEN :la_sku ELSE :zgz_sku END, "
                "1 + (n % 7), CASE WHEN n % 10 = 0 THEN 'loss' ELSE 'dispatch' END, "
                "CASE WHEN n % 10 = 0 THEN NULL ELSE 'perf-dispatch-' || n END, "
                "CASE WHEN n % 2 = 0 THEN 'LA' ELSE 'ZGZ' END, "
                ":start + ((n % :hours) * interval '1 hour') + ((n % 3600) * interval '1 second'), "
                ":user_id FROM generate_series(1, :row_count) AS n"
            ),
            {
                "la_sku": sku_by_warehouse["LA"],
                "zgz_sku": sku_by_warehouse["ZGZ"],
                "start": start,
                "hours": total_hours,
                "user_id": user_id,
                "row_count": per_source,
            },
        )
        connection.execute(
            text(
                "INSERT INTO stockout_events "
                "(sku_id, warehouse, client_id, threshold_at_event, stock_after, stock_exit_id, occurred_at) "
                "SELECT sku_id, warehouse, :client, 1, 0, id, created_at FROM stock_exits "
                "WHERE exit_type = 'dispatch' ORDER BY id LIMIT 10000"
            ),
            {"client": client_id},
        )
        connection.execute(
            text(
                "INSERT INTO inventory_discrepancies "
                "(stock_exit_id, sku_id, warehouse, client_id, quantity_delta, source, detected_at) "
                "SELECT id, sku_id, warehouse, :client, 1, 'feed', created_at FROM stock_exits "
                "WHERE exit_type = 'dispatch' ORDER BY id LIMIT 10000"
            ),
            {"client": client_id},
        )


def _max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _clear_projection(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE inventory_discrepancies, stockout_events, stock_exits, stock_entries, "
                "skus, clients, reporting.hourly_activity_rollups, reporting.rollup_state, "
                "reporting.pipeline_runs, reporting.source_ledger_state "
                "RESTART IDENTITY CASCADE"
            )
        )
        connection.execute(
            text(
                "INSERT INTO reporting.source_ledger_state (id, updated_at) VALUES (1, now())"
            )
        )
        connection.execute(text("INSERT INTO reporting.rollup_state (id) VALUES (1)"))


def test_rollup_budgets_at_twice_projected_six_month_volume(
    pipeline_engine: Engine,
    request: pytest.FixtureRequest,
) -> None:
    if os.environ.get("REPORTING_PERFORMANCE_TEST") != "1":
        pytest.skip("set REPORTING_PERFORMANCE_TEST=1 for the production-volume gate")

    request.addfinalizer(lambda: _clear_projection(pipeline_engine))
    start = datetime(2024, 6, 3, 14, tzinfo=UTC)
    cutoff = datetime(2026, 7, 28, 18, tzinfo=UTC)
    _seed_projection(pipeline_engine, start=start, end=cutoff)
    enqueue_cli(pipeline_engine, now=cutoff - timedelta(seconds=1))
    claim = claim_next(pipeline_engine, now=cutoff)
    assert claim is not None
    window = RollupWindow(
        start=start,
        end=cutoff,
        source_cutoff_at=cutoff,
        rows_scanned=TOTAL_MOVEMENTS + 20_000,
    )

    aggregate_started = perf_counter()
    rows = compute_hourly_rollups(pipeline_engine, window)
    aggregate_seconds = perf_counter() - aggregate_started
    publish_started = perf_counter()
    written = publish_hourly_rollups(
        pipeline_engine,
        claim,
        window,
        rows,
        now=cutoff,
    )
    publish_seconds = perf_counter() - publish_started

    regular_window = RollupWindow(
        start=cutoff - timedelta(hours=72),
        end=cutoff,
        source_cutoff_at=cutoff,
        rows_scanned=0,
    )
    regular_started = perf_counter()
    regular_rows = compute_hourly_rollups(pipeline_engine, regular_window)
    regular_seconds = perf_counter() - regular_started

    reconciliation_started = perf_counter()
    reconciliation = reconcile_hourly_rollups(
        pipeline_engine,
        start=start,
        cutoff=cutoff,
    )
    reconciliation_seconds = perf_counter() - reconciliation_started

    read_started = perf_counter()
    with pipeline_engine.connect() as connection:
        report_rows = list(
            connection.execute(
                text(
                    "SELECT date_trunc('week', bucket_start), warehouse, client_id, "
                    "sum(inbound_units), sum(dispatch_order_count), sum(stockout_count), "
                    "sum(discrepancy_count) FROM reporting.hourly_activity_rollups "
                    "WHERE bucket_start >= :start AND bucket_start < :cutoff "
                    "GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
                ),
                {"start": start, "cutoff": cutoff},
            )
        )
    read_seconds = perf_counter() - read_started

    print(
        "rollup_performance "
        f"source_rows={window.rows_scanned} rollup_rows={written} "
        f"full_aggregate_seconds={aggregate_seconds:.3f} "
        f"full_publish_seconds={publish_seconds:.3f} "
        f"regular_seconds={regular_seconds:.3f} "
        f"reconciliation_seconds={reconciliation_seconds:.3f} "
        f"read_seconds={read_seconds:.3f} max_rss_bytes={_max_rss_bytes()}"
    )
    assert written == len(rows)
    assert written == OBSERVED_PRODUCTION_DENSE_ROWS
    assert regular_rows
    assert reconciliation.exact
    assert report_rows
    assert aggregate_seconds <= 30
    assert aggregate_seconds + publish_seconds <= 60
    assert regular_seconds <= 60
    assert read_seconds <= 2
    assert _max_rss_bytes() <= int(WORKER_LIMIT_BYTES * 0.8)
