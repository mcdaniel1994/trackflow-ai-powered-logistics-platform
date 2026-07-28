"""Durable SQL hourly rollups and exact raw-source reconciliation."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Engine, RowMapping, text

from .queue import RunClaim, engine_from_environment, verify_claim_for_publication

ROLLUP_PIPELINE_VERSION: Final = "engagement-6-phase-6.2"
ROLLUP_STATEMENT_TIMEOUT_MS: Final = 60_000
TRAILING_RECOMPUTE_HOURS: Final = 72
ROLLUP_FEATURE_FLAG: Final = "REPORTING_HOURLY_ROLLUPS_ENABLED"


class RollupValidationError(RuntimeError):
    """Raised when rollup inputs or aggregate invariants are invalid."""


@dataclass(frozen=True)
class RollupWindow:
    start: datetime
    end: datetime
    source_cutoff_at: datetime
    rows_scanned: int


@dataclass(frozen=True)
class HourlyRollupRow:
    bucket_start: datetime
    warehouse: str
    client_id: UUID
    inbound_movement_count: int
    inbound_units: int
    dispatch_order_count: int
    dispatch_units: int
    loss_movement_count: int
    loss_units: int
    stockout_count: int
    discrepancy_count: int


@dataclass(frozen=True)
class ReconciliationMismatch:
    week_start: date
    warehouse: str
    client_id: UUID
    metrics: tuple[str, ...]


@dataclass(frozen=True)
class ReconciliationResult:
    checked_dimensions: int
    mismatches: tuple[ReconciliationMismatch, ...]

    @property
    def exact(self) -> bool:
        return not self.mismatches


def hourly_rollups_enabled() -> bool:
    """Return the opt-in shadow-computation flag; absence is always off."""
    return os.environ.get(ROLLUP_FEATURE_FLAG, "false").strip().lower() == "true"


def _floor_hour(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RollupValidationError("rollup cutoff must be timezone-aware")
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _statement_timeout(connection: Any) -> None:
    connection.execute(text(f"SET LOCAL statement_timeout = '{ROLLUP_STATEMENT_TIMEOUT_MS}ms'"))


def _source_floor(connection: Any) -> datetime | None:
    return cast(
        datetime | None,
        connection.scalar(
            text(
                "SELECT min(source_at) FROM ("
                " SELECT min(created_at) AS source_at FROM stock_entries"
                " UNION ALL SELECT min(created_at) FROM stock_exits"
                " UNION ALL SELECT min(occurred_at) FROM stockout_events"
                " UNION ALL SELECT min(detected_at) FROM inventory_discrepancies"
                ") AS source_minima"
            )
        ),
    )


def _count_source_rows(connection: Any, start: datetime, end: datetime) -> int:
    return int(
        connection.scalar(
            text(
                "SELECT "
                "(SELECT count(*) FROM stock_entries WHERE created_at >= :start AND created_at < :end) + "
                "(SELECT count(*) FROM stock_exits WHERE created_at >= :start AND created_at < :end) + "
                "(SELECT count(*) FROM stockout_events WHERE occurred_at >= :start AND occurred_at < :end) + "
                "(SELECT count(*) FROM inventory_discrepancies "
                " WHERE detected_at >= :start AND detected_at < :end)"
            ),
            {"start": start, "end": end},
        )
        or 0
    )


def capture_rollup_window(
    engine: Engine,
    claim: RunClaim,
    *,
    now: datetime | None = None,
) -> RollupWindow:
    """Capture one immutable completed-hour cutoff and its recomputation window."""
    cutoff = _floor_hour(now or datetime.now(UTC))
    with engine.begin() as connection:
        _statement_timeout(connection)
        state = connection.execute(
            text(
                "SELECT rollup.last_cutoff_at, ledger.last_reset_at "
                "FROM reporting.rollup_state AS rollup "
                "CROSS JOIN reporting.source_ledger_state AS ledger "
                "WHERE rollup.id = 1 AND ledger.id = 1"
            )
        ).mappings().one()
        last_cutoff = cast(datetime | None, state["last_cutoff_at"])
        last_reset = cast(datetime | None, state["last_reset_at"])

        if claim.requested_week_start is not None:
            start = datetime.combine(claim.requested_week_start, time.min, tzinfo=UTC)
            end = min(start + timedelta(days=7), cutoff)
        else:
            trailing_start = cutoff - timedelta(hours=TRAILING_RECOMPUTE_HOURS)
            if last_cutoff is not None:
                start = min(_floor_hour(last_cutoff), trailing_start)
            else:
                earliest = _source_floor(connection)
                start = _floor_hour(earliest) if earliest is not None else trailing_start
            end = cutoff

        if last_reset is not None:
            start = max(start, _floor_hour(last_reset))
        if start >= end:
            raise RollupValidationError("rollup window contains no completed UTC hour")
        return RollupWindow(
            start=start,
            end=end,
            source_cutoff_at=cutoff,
            rows_scanned=_count_source_rows(connection, start, end),
        )


_ROLLUP_QUERY = text(
    "WITH buckets AS ("
    " SELECT generate_series(:start, :end - interval '1 hour', interval '1 hour') AS bucket_start"
    "), dimensions AS ("
    " SELECT DISTINCT warehouse, client_id FROM skus"
    "), inbound AS ("
    " SELECT date_trunc('hour', entry.created_at) AS bucket_start, entry.warehouse, sku.client_id, "
    " count(*)::bigint AS movement_count, sum(entry.quantity)::bigint AS units "
    " FROM stock_entries AS entry JOIN skus AS sku ON sku.id = entry.sku_id "
    " WHERE entry.created_at >= :start AND entry.created_at < :end "
    " GROUP BY 1, 2, 3"
    "), outbound AS ("
    " SELECT date_trunc('hour', movement.created_at) AS bucket_start, movement.warehouse, sku.client_id, "
    " count(*) FILTER (WHERE movement.exit_type = 'dispatch')::bigint AS dispatch_count, "
    " COALESCE(sum(movement.quantity) FILTER (WHERE movement.exit_type = 'dispatch'), 0)::bigint "
    " AS dispatch_units, "
    " count(*) FILTER (WHERE movement.exit_type = 'loss')::bigint AS loss_count, "
    " COALESCE(sum(movement.quantity) FILTER (WHERE movement.exit_type = 'loss'), 0)::bigint AS loss_units "
    " FROM stock_exits AS movement JOIN skus AS sku ON sku.id = movement.sku_id "
    " WHERE movement.created_at >= :start AND movement.created_at < :end "
    " GROUP BY 1, 2, 3"
    "), stockouts AS ("
    " SELECT date_trunc('hour', occurred_at) AS bucket_start, warehouse, client_id, "
    " count(*)::bigint AS event_count FROM stockout_events "
    " WHERE occurred_at >= :start AND occurred_at < :end GROUP BY 1, 2, 3"
    "), discrepancies AS ("
    " SELECT date_trunc('hour', detected_at) AS bucket_start, warehouse, client_id, "
    " count(*)::bigint AS event_count FROM inventory_discrepancies "
    " WHERE detected_at >= :start AND detected_at < :end GROUP BY 1, 2, 3"
    ") SELECT bucket.bucket_start, dimension.warehouse, dimension.client_id, "
    "COALESCE(inbound.movement_count, 0) AS inbound_movement_count, "
    "COALESCE(inbound.units, 0) AS inbound_units, "
    "COALESCE(outbound.dispatch_count, 0) AS dispatch_order_count, "
    "COALESCE(outbound.dispatch_units, 0) AS dispatch_units, "
    "COALESCE(outbound.loss_count, 0) AS loss_movement_count, "
    "COALESCE(outbound.loss_units, 0) AS loss_units, "
    "COALESCE(stockouts.event_count, 0) AS stockout_count, "
    "COALESCE(discrepancies.event_count, 0) AS discrepancy_count "
    "FROM buckets AS bucket CROSS JOIN dimensions AS dimension "
    "LEFT JOIN inbound USING (bucket_start, warehouse, client_id) "
    "LEFT JOIN outbound USING (bucket_start, warehouse, client_id) "
    "LEFT JOIN stockouts USING (bucket_start, warehouse, client_id) "
    "LEFT JOIN discrepancies USING (bucket_start, warehouse, client_id) "
    "ORDER BY bucket.bucket_start, dimension.warehouse, dimension.client_id"
)


def _rollup_row(row: RowMapping) -> HourlyRollupRow:
    client_id = row["client_id"]
    return HourlyRollupRow(
        bucket_start=cast(datetime, row["bucket_start"]),
        warehouse=cast(str, row["warehouse"]),
        client_id=client_id if isinstance(client_id, UUID) else UUID(str(client_id)),
        inbound_movement_count=int(row["inbound_movement_count"]),
        inbound_units=int(row["inbound_units"]),
        dispatch_order_count=int(row["dispatch_order_count"]),
        dispatch_units=int(row["dispatch_units"]),
        loss_movement_count=int(row["loss_movement_count"]),
        loss_units=int(row["loss_units"]),
        stockout_count=int(row["stockout_count"]),
        discrepancy_count=int(row["discrepancy_count"]),
    )


def compute_hourly_rollups(engine: Engine, window: RollupWindow) -> list[HourlyRollupRow]:
    """Aggregate each raw source independently in SQL into a dense hourly grid."""
    with engine.begin() as connection:
        _statement_timeout(connection)
        rows = connection.execute(
            _ROLLUP_QUERY,
            {"start": window.start, "end": window.end},
        ).mappings()
        return [_rollup_row(row) for row in rows]


_UPSERT = text(
    "INSERT INTO reporting.hourly_activity_rollups "
    "(bucket_start, warehouse, client_id, inbound_movement_count, inbound_units, "
    "dispatch_order_count, dispatch_units, loss_movement_count, loss_units, "
    "stockout_count, discrepancy_count, source_cutoff_at, computed_at, pipeline_version) "
    "VALUES (:bucket_start, :warehouse, :client_id, :inbound_movement_count, :inbound_units, "
    ":dispatch_order_count, :dispatch_units, :loss_movement_count, :loss_units, "
    ":stockout_count, :discrepancy_count, :source_cutoff_at, :computed_at, :pipeline_version) "
    "ON CONFLICT (bucket_start, warehouse, client_id) DO UPDATE SET "
    "inbound_movement_count = EXCLUDED.inbound_movement_count, "
    "inbound_units = EXCLUDED.inbound_units, "
    "dispatch_order_count = EXCLUDED.dispatch_order_count, "
    "dispatch_units = EXCLUDED.dispatch_units, "
    "loss_movement_count = EXCLUDED.loss_movement_count, "
    "loss_units = EXCLUDED.loss_units, "
    "stockout_count = EXCLUDED.stockout_count, "
    "discrepancy_count = EXCLUDED.discrepancy_count, "
    "source_cutoff_at = EXCLUDED.source_cutoff_at, "
    "computed_at = EXCLUDED.computed_at, "
    "pipeline_version = EXCLUDED.pipeline_version"
)


def publish_hourly_rollups(
    engine: Engine,
    claim: RunClaim,
    window: RollupWindow,
    rows: list[HourlyRollupRow],
    *,
    pipeline_version: str = ROLLUP_PIPELINE_VERSION,
    now: datetime | None = None,
) -> int:
    """Publish idempotently and advance the singleton cursor in the same transaction."""
    computed_at = now or datetime.now(UTC)
    payloads = [
        {
            **row.__dict__,
            "source_cutoff_at": window.source_cutoff_at,
            "computed_at": computed_at,
            "pipeline_version": pipeline_version,
        }
        for row in rows
    ]
    with engine.begin() as connection:
        _statement_timeout(connection)
        verify_claim_for_publication(connection, claim)
        if payloads:
            connection.execute(_UPSERT, payloads)
        connection.execute(
            text(
                "UPDATE reporting.rollup_state SET pipeline_version = :pipeline_version, "
                "last_cutoff_at = GREATEST(COALESCE(last_cutoff_at, :cutoff), :cutoff), "
                "last_published_at = :published_at WHERE id = 1"
            ),
            {
                "pipeline_version": pipeline_version,
                "cutoff": window.source_cutoff_at,
                "published_at": computed_at,
            },
        )
    return len(rows)


_RECONCILIATION_QUERY = text(
    "WITH inbound AS ("
    " SELECT date_trunc('week', entry.created_at)::date AS week_start, entry.warehouse, sku.client_id, "
    " count(*)::bigint AS inbound_movement_count, sum(entry.quantity)::bigint AS inbound_units "
    " FROM stock_entries AS entry JOIN skus AS sku ON sku.id = entry.sku_id "
    " WHERE entry.created_at >= :start AND entry.created_at < :end GROUP BY 1, 2, 3"
    "), outbound AS ("
    " SELECT date_trunc('week', movement.created_at)::date AS week_start, movement.warehouse, sku.client_id, "
    " count(*) FILTER (WHERE movement.exit_type = 'dispatch')::bigint AS dispatch_order_count, "
    " COALESCE(sum(movement.quantity) FILTER (WHERE movement.exit_type = 'dispatch'), 0)::bigint "
    " AS dispatch_units, "
    " count(*) FILTER (WHERE movement.exit_type = 'loss')::bigint AS loss_movement_count, "
    " COALESCE(sum(movement.quantity) FILTER (WHERE movement.exit_type = 'loss'), 0)::bigint AS loss_units "
    " FROM stock_exits AS movement JOIN skus AS sku ON sku.id = movement.sku_id "
    " WHERE movement.created_at >= :start AND movement.created_at < :end GROUP BY 1, 2, 3"
    "), stockouts AS ("
    " SELECT date_trunc('week', occurred_at)::date AS week_start, warehouse, client_id, "
    " count(*)::bigint AS stockout_count FROM stockout_events "
    " WHERE occurred_at >= :start AND occurred_at < :end GROUP BY 1, 2, 3"
    "), discrepancies AS ("
    " SELECT date_trunc('week', detected_at)::date AS week_start, warehouse, client_id, "
    " count(*)::bigint AS discrepancy_count FROM inventory_discrepancies "
    " WHERE detected_at >= :start AND detected_at < :end GROUP BY 1, 2, 3"
    "), actual AS ("
    " SELECT date_trunc('week', bucket_start)::date AS week_start, warehouse, client_id, "
    " sum(inbound_movement_count)::bigint AS inbound_movement_count, "
    " sum(inbound_units)::bigint AS inbound_units, "
    " sum(dispatch_order_count)::bigint AS dispatch_order_count, "
    " sum(dispatch_units)::bigint AS dispatch_units, "
    " sum(loss_movement_count)::bigint AS loss_movement_count, "
    " sum(loss_units)::bigint AS loss_units, "
    " sum(stockout_count)::bigint AS stockout_count, "
    " sum(discrepancy_count)::bigint AS discrepancy_count "
    " FROM reporting.hourly_activity_rollups "
    " WHERE bucket_start >= :start AND bucket_start < :end GROUP BY 1, 2, 3"
    "), keys AS ("
    " SELECT week_start, warehouse, client_id FROM inbound UNION "
    " SELECT week_start, warehouse, client_id FROM outbound UNION "
    " SELECT week_start, warehouse, client_id FROM stockouts UNION "
    " SELECT week_start, warehouse, client_id FROM discrepancies UNION "
    " SELECT week_start, warehouse, client_id FROM actual"
    ") SELECT keys.week_start, keys.warehouse, keys.client_id, "
    "COALESCE(inbound.inbound_movement_count, 0) AS expected_inbound_movement_count, "
    "COALESCE(actual.inbound_movement_count, 0) AS actual_inbound_movement_count, "
    "COALESCE(inbound.inbound_units, 0) AS expected_inbound_units, "
    "COALESCE(actual.inbound_units, 0) AS actual_inbound_units, "
    "COALESCE(outbound.dispatch_order_count, 0) AS expected_dispatch_order_count, "
    "COALESCE(actual.dispatch_order_count, 0) AS actual_dispatch_order_count, "
    "COALESCE(outbound.dispatch_units, 0) AS expected_dispatch_units, "
    "COALESCE(actual.dispatch_units, 0) AS actual_dispatch_units, "
    "COALESCE(outbound.loss_movement_count, 0) AS expected_loss_movement_count, "
    "COALESCE(actual.loss_movement_count, 0) AS actual_loss_movement_count, "
    "COALESCE(outbound.loss_units, 0) AS expected_loss_units, "
    "COALESCE(actual.loss_units, 0) AS actual_loss_units, "
    "COALESCE(stockouts.stockout_count, 0) AS expected_stockout_count, "
    "COALESCE(actual.stockout_count, 0) AS actual_stockout_count, "
    "COALESCE(discrepancies.discrepancy_count, 0) AS expected_discrepancy_count, "
    "COALESCE(actual.discrepancy_count, 0) AS actual_discrepancy_count "
    "FROM keys LEFT JOIN inbound USING (week_start, warehouse, client_id) "
    "LEFT JOIN outbound USING (week_start, warehouse, client_id) "
    "LEFT JOIN stockouts USING (week_start, warehouse, client_id) "
    "LEFT JOIN discrepancies USING (week_start, warehouse, client_id) "
    "LEFT JOIN actual USING (week_start, warehouse, client_id) "
    "ORDER BY keys.week_start, keys.warehouse, keys.client_id"
)

_METRICS: Final = (
    "inbound_movement_count",
    "inbound_units",
    "dispatch_order_count",
    "dispatch_units",
    "loss_movement_count",
    "loss_units",
    "stockout_count",
    "discrepancy_count",
)


def reconcile_hourly_rollups(
    engine: Engine,
    *,
    start: datetime,
    cutoff: datetime,
    mark_reconciled: bool = True,
) -> ReconciliationResult:
    """Compare rollup sums with direct raw SQL aggregation at one fixed cutoff."""
    start_at = _floor_hour(start)
    end_at = _floor_hour(cutoff)
    if start_at >= end_at:
        raise RollupValidationError("reconciliation window contains no completed UTC hour")
    with engine.begin() as connection:
        _statement_timeout(connection)
        rows = list(
            connection.execute(
                _RECONCILIATION_QUERY,
                {"start": start_at, "end": end_at},
            ).mappings()
        )
        mismatches: list[ReconciliationMismatch] = []
        for row in rows:
            differing = tuple(
                metric
                for metric in _METRICS
                if int(row[f"expected_{metric}"]) != int(row[f"actual_{metric}"])
            )
            if int(row["actual_discrepancy_count"]) > int(row["actual_dispatch_order_count"]):
                differing = (*differing, "discrepancy_rate_denominator")
            if differing:
                raw_client_id = row["client_id"]
                mismatches.append(
                    ReconciliationMismatch(
                        week_start=cast(date, row["week_start"]),
                        warehouse=cast(str, row["warehouse"]),
                        client_id=(
                            raw_client_id
                            if isinstance(raw_client_id, UUID)
                            else UUID(str(raw_client_id))
                        ),
                        metrics=differing,
                    )
                )
        if not mismatches and mark_reconciled:
            connection.execute(
                text(
                    "UPDATE reporting.rollup_state SET last_reconciled_at = :now "
                    "WHERE id = 1 AND last_cutoff_at >= :cutoff"
                ),
                {"now": datetime.now(UTC), "cutoff": end_at},
            )
    return ReconciliationResult(len(rows), tuple(mismatches))


def _parse_instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile durable hourly rollups with raw sources")
    parser.add_argument("--start", required=True, type=_parse_instant)
    parser.add_argument("--cutoff", required=True, type=_parse_instant)
    args = parser.parse_args()
    engine = engine_from_environment()
    try:
        result = reconcile_hourly_rollups(engine, start=args.start, cutoff=args.cutoff)
    finally:
        engine.dispose()
    if not result.exact:
        print(f"reporting_rollup_reconciliation=failed mismatches={len(result.mismatches)}")
        raise SystemExit(1)
    print(f"reporting_rollup_reconciliation=passed dimensions={result.checked_dimensions}")


if __name__ == "__main__":  # pragma: no cover - module entrypoint
    main()
