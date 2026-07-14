"""Prefect-as-library ETL flows for weekly warehouse/client performance."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Final, cast
from uuid import UUID

from prefect import flow, task
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from process.business_performance import (
    Activity,
    TransformError,
    WeeklyPerformanceRow,
    assemble_weekly_rows,
    source_content_digest,
)

from .cache import (
    CACHE_TTL,
    EVALUATION_VERSION,
    CacheConfigurationError,
    CacheParameters,
    cache_store_from_environment,
    prefect_transformation_cache_key,
    transform_with_cache,
)
from .queue import (
    DEFAULT_RECOMPUTE_WEEKS,
    ErrorCode,
    LeaseLostError,
    RunClaim,
    RunMetrics,
    engine_from_environment,
    finalize_failure,
    finalize_success,
    heartbeat,
    release_retryable,
    verify_claim_for_publication,
)
from .runner import FinalizedExecution, RunnerStatus

EXTRACTION_RETRIES: Final = 3
EXTRACTION_RETRY_DELAY_SECONDS: Final = 10


@dataclass(frozen=True)
class WarehouseClientActivity:
    activity: dict[str, list[dict[str, object]]]
    sku_pairs: tuple[tuple[str, str], ...]
    source_watermark: datetime | None
    source_digest: str
    rows_extracted: int


@dataclass(frozen=True)
class TransformResult:
    rows: list[WeeklyPerformanceRow]
    cache_hit: bool


@dataclass(frozen=True)
class LoadResult:
    rows_loaded: int
    run_ts: datetime


def _engine() -> Engine:
    return engine_from_environment()


def _extract_records(query: str, start: datetime, end: datetime) -> list[dict[str, object]]:
    engine = _engine()
    try:
        with engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(query), {"start": start, "end": end}).mappings()]
    finally:
        engine.dispose()


@task(retries=EXTRACTION_RETRIES, retry_delay_seconds=EXTRACTION_RETRY_DELAY_SECONDS, persist_result=False)
def extract_inbound_order_created(start: datetime, end: datetime) -> list[dict[str, object]]:
    # These reads are immutable and idempotent; three short retries absorb
    # transient pooler blips without concealing a sustained source outage.
    return _extract_records(
        "SELECT entry.id, entry.created_at AS occurred_at, entry.quantity, "
        "entry.warehouse, sku.client_id FROM stock_entries AS entry "
        "JOIN skus AS sku ON sku.id = entry.sku_id "
        "WHERE entry.created_at >= :start AND entry.created_at < :end ORDER BY entry.id",
        start,
        end,
    )


@task(retries=EXTRACTION_RETRIES, retry_delay_seconds=EXTRACTION_RETRY_DELAY_SECONDS, persist_result=False)
def extract_outbound_order_created(start: datetime, end: datetime) -> list[dict[str, object]]:
    return _extract_records(
        "SELECT movement.id, movement.created_at AS occurred_at, movement.quantity, "
        "movement.warehouse, sku.client_id FROM stock_exits AS movement "
        "JOIN skus AS sku ON sku.id = movement.sku_id "
        "WHERE movement.created_at >= :start AND movement.created_at < :end ORDER BY movement.id",
        start,
        end,
    )


@task(retries=EXTRACTION_RETRIES, retry_delay_seconds=EXTRACTION_RETRY_DELAY_SECONDS, persist_result=False)
def extract_stock_threshold_triggered(start: datetime, end: datetime) -> list[dict[str, object]]:
    return _extract_records(
        "SELECT id, occurred_at, warehouse, client_id FROM stockout_events "
        "WHERE occurred_at >= :start AND occurred_at < :end ORDER BY id",
        start,
        end,
    )


@task(retries=EXTRACTION_RETRIES, retry_delay_seconds=EXTRACTION_RETRY_DELAY_SECONDS, persist_result=False)
def extract_inventory_discrepancy_detected(start: datetime, end: datetime) -> list[dict[str, object]]:
    return _extract_records(
        "SELECT id, detected_at AS occurred_at, quantity_delta, warehouse, client_id "
        "FROM inventory_discrepancies "
        "WHERE detected_at >= :start AND detected_at < :end ORDER BY id",
        start,
        end,
    )


@task(persist_result=False)
def extract_sku_pairs() -> tuple[tuple[str, str], ...]:
    engine = _engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT DISTINCT warehouse, client_id FROM skus ORDER BY warehouse, client_id")
            ).all()
            return tuple((cast(str, warehouse), str(client_id)) for warehouse, client_id in rows)
    finally:
        engine.dispose()


@flow(name="extract_warehouse_client_activity", persist_result=False)
def extract_warehouse_client_activity(target_weeks: tuple[date, ...]) -> WarehouseClientActivity:
    if not target_weeks:
        raise TransformError("target_weeks must not be empty")
    start = datetime.combine(min(target_weeks), time.min, tzinfo=UTC)
    end = datetime.combine(max(target_weeks) + timedelta(days=7), time.min, tzinfo=UTC)
    activity: dict[str, list[dict[str, object]]] = {
        "inbound_order_created": extract_inbound_order_created(start, end),
        "outbound_order_created": extract_outbound_order_created(start, end),
        "stock_threshold_triggered": extract_stock_threshold_triggered(start, end),
        "inventory_discrepancy_detected": extract_inventory_discrepancy_detected(start, end),
    }
    sku_pairs = extract_sku_pairs()
    timestamps = [
        cast(datetime, record["occurred_at"])
        for records in activity.values()
        for record in records
    ]
    return WarehouseClientActivity(
        activity=activity,
        sku_pairs=sku_pairs,
        source_watermark=max(timestamps) if timestamps else None,
        source_digest=source_content_digest(activity),
        rows_extracted=sum(len(records) for records in activity.values()),
    )


@task(
    cache_key_fn=prefect_transformation_cache_key,
    cache_expiration=CACHE_TTL,
    persist_result=False,
)
def assemble_weekly_rows_cached(
    activity: Activity,
    sku_pairs: tuple[tuple[str, str], ...],
    target_weeks: tuple[date, ...],
    last_reset_at: datetime | None,
    source_digest: str,
    pipeline_version: str,
    evaluation_version: str,
    recompute_weeks: int,
    cache_nonce: UUID | None,
) -> TransformResult:
    if source_content_digest(activity) != source_digest:
        raise TransformError("source digest does not match extracted content")
    cached = transform_with_cache(
        cache_store_from_environment(),
        CacheParameters(
            source_digest=source_digest,
            pipeline_version=pipeline_version,
            evaluation_version=evaluation_version,
            target_weeks=target_weeks,
            recompute_weeks=recompute_weeks,
            sku_pairs=sku_pairs,
            last_reset_at=last_reset_at,
            cache_nonce=cache_nonce,
        ),
        lambda: assemble_weekly_rows(
            activity,
            sku_pairs=sku_pairs,
            target_weeks=target_weeks,
            last_reset_at=last_reset_at,
        ),
    )
    return TransformResult(cached.rows, cached.cache_hit)


@task(persist_result=False)
def validate_weekly_rows(rows: list[WeeklyPerformanceRow]) -> list[WeeklyPerformanceRow]:
    for row in rows:
        if row.discrepancy_events_count > row.outbound_orders_count:
            raise TransformError("discrepancy events cannot exceed outbound orders")
        if row.week_start.isoweekday() != 1:
            raise TransformError("weekly rows must start on Monday")
    return rows


@flow(name="transform_weekly_performance", persist_result=False)
def transform_weekly_performance(
    extracted: WarehouseClientActivity,
    claim: RunClaim,
    *,
    last_reset_at: datetime | None,
    pipeline_version: str,
) -> TransformResult:
    transformed = assemble_weekly_rows_cached(
        extracted.activity,
        extracted.sku_pairs,
        claim.target_weeks,
        last_reset_at,
        extracted.source_digest,
        pipeline_version,
        EVALUATION_VERSION,
        DEFAULT_RECOMPUTE_WEEKS,
        _cache_nonce(claim.run_id),
    )
    return TransformResult(validate_weekly_rows(transformed.rows), transformed.cache_hit)


def _cache_nonce(run_id: UUID) -> UUID | None:
    engine = _engine()
    try:
        with engine.connect() as connection:
            return cast(
                UUID | None,
                connection.execute(
                    text("SELECT cache_nonce FROM reporting.pipeline_runs WHERE id = :id"),
                    {"id": run_id},
                ).scalar_one(),
            )
    finally:
        engine.dispose()


def _last_reset_at() -> datetime | None:
    engine = _engine()
    try:
        with engine.connect() as connection:
            return cast(
                datetime | None,
                connection.execute(
                    text("SELECT last_reset_at FROM reporting.source_ledger_state WHERE id = 1")
                ).scalar_one_or_none(),
            )
    finally:
        engine.dispose()


@task(retries=3, retry_delay_seconds=10, persist_result=False)
def upsert_weekly_performance_rows(rows: list[WeeklyPerformanceRow], claim: RunClaim) -> LoadResult:
    engine = _engine()
    run_ts = datetime.now(UTC)
    keys = json.dumps(
        [
            {"warehouse": row.warehouse, "client_id": row.client_id, "week_start": row.week_start.isoformat()}
            for row in rows
        ]
    )
    try:
        with engine.begin() as connection:
            # Claim verification and publication share this transaction, so a
            # reclaimed worker cannot commit even if it finished expensive work.
            verify_claim_for_publication(connection, claim)
            for row in rows:
                connection.execute(
                    text(
                        "INSERT INTO reporting.weekly_warehouse_client_performance "
                        "(warehouse, client_id, week_start, inbound_units_count, outbound_orders_count, "
                        " stockout_events_count, discrepancy_events_count, discrepancy_rate, computed_at) "
                        "VALUES (:warehouse, :client_id, :week_start, :inbound, :outbound, :stockouts, "
                        " :discrepancies, :rate, :computed_at) "
                        "ON CONFLICT (warehouse, client_id, week_start) DO UPDATE SET "
                        "inbound_units_count = EXCLUDED.inbound_units_count, "
                        "outbound_orders_count = EXCLUDED.outbound_orders_count, "
                        "stockout_events_count = EXCLUDED.stockout_events_count, "
                        "discrepancy_events_count = EXCLUDED.discrepancy_events_count, "
                        "discrepancy_rate = EXCLUDED.discrepancy_rate, computed_at = EXCLUDED.computed_at"
                    ),
                    {
                        "warehouse": row.warehouse,
                        "client_id": row.client_id,
                        "week_start": row.week_start,
                        "inbound": row.inbound_units_count,
                        "outbound": row.outbound_orders_count,
                        "stockouts": row.stockout_events_count,
                        "discrepancies": row.discrepancy_events_count,
                        "rate": row.discrepancy_rate,
                        "computed_at": run_ts,
                    },
                )
            connection.execute(
                text(
                    "DELETE FROM reporting.weekly_warehouse_client_performance AS report "
                    "WHERE report.week_start = ANY(CAST(:weeks AS date[])) "
                    "AND NOT EXISTS (SELECT 1 FROM jsonb_to_recordset(CAST(:keys AS jsonb)) "
                    "AS keep(warehouse text, client_id uuid, week_start date) "
                    "WHERE keep.warehouse = report.warehouse AND keep.client_id = report.client_id "
                    "AND keep.week_start = report.week_start)"
                ),
                {"weeks": list(claim.target_weeks), "keys": keys},
            )
        return LoadResult(len(rows), run_ts)
    finally:
        engine.dispose()


@flow(name="load_weekly_performance_report", persist_result=False)
def load_weekly_performance_report(rows: list[WeeklyPerformanceRow], claim: RunClaim) -> LoadResult:
    return upsert_weekly_performance_rows(rows, claim)


@task(persist_result=False)
def renew_pipeline_lease(claim: RunClaim) -> None:
    engine = _engine()
    try:
        if not heartbeat(engine, claim):
            raise LeaseLostError("pipeline run lease is no longer owned")
    finally:
        engine.dispose()


@flow(name="finalize_pipeline_run", persist_result=False)
def finalize_pipeline_run(
    claim: RunClaim,
    *,
    metrics: RunMetrics | None,
    status: RunnerStatus,
    error_code: ErrorCode | None = None,
) -> FinalizedExecution:
    engine = _engine()
    try:
        if status == RunnerStatus.SUCCEEDED and metrics is not None:
            transitioned = finalize_success(engine, claim, metrics)
        elif status == RunnerStatus.FAILED:
            transitioned = finalize_failure(engine, claim, error_code or "VALIDATE_FAILED")
        else:
            transitioned = release_retryable(engine, claim, error_code or "DB_UNAVAILABLE")
        return FinalizedExecution(status if transitioned else RunnerStatus.LEASE_LOST)
    finally:
        engine.dispose()


@task(persist_result=False)
def publish_run_summary(run_id: UUID, status: RunnerStatus, metrics: RunMetrics | None) -> None:
    if os.environ.get("REPORTING_EVAL_OUTPUT_ENABLED", "false").lower() != "true":
        return
    output_dir = Path(__file__).resolve().parents[2] / "eval" / "business_performance"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": str(run_id),
        "status": status.value,
        "rows_extracted": metrics.rows_extracted if metrics else None,
        "rows_transformed": metrics.rows_transformed if metrics else None,
        "rows_loaded": metrics.rows_loaded if metrics else None,
    }
    (output_dir / f"{run_id}.json").write_text(json.dumps(payload, sort_keys=True) + "\n")


@flow(name="weekly_warehouse_client_performance", persist_result=False)
def weekly_warehouse_client_performance(claim: RunClaim, pipeline_version: str) -> FinalizedExecution:
    metrics: RunMetrics | None = None
    final_status = RunnerStatus.RETRYABLE
    try:
        extracted = extract_warehouse_client_activity(claim.target_weeks)
        renew_pipeline_lease(claim)
        transformed = transform_weekly_performance(
            extracted,
            claim,
            last_reset_at=_last_reset_at(),
            pipeline_version=pipeline_version,
        )
        renew_pipeline_lease(claim)
        loaded = load_weekly_performance_report(transformed.rows, claim)
        metrics = RunMetrics(
            rows_extracted=extracted.rows_extracted,
            rows_transformed=len(transformed.rows),
            rows_loaded=loaded.rows_loaded,
            source_watermark=extracted.source_watermark,
        )
        final_status = RunnerStatus.SUCCEEDED
        result = finalize_pipeline_run(claim, metrics=metrics, status=final_status)
    except (TransformError, CacheConfigurationError):
        final_status = RunnerStatus.FAILED
        result = finalize_pipeline_run(
            claim,
            metrics=None,
            status=final_status,
            error_code="VALIDATE_FAILED",
        )
    except LeaseLostError:
        final_status = RunnerStatus.LEASE_LOST
        result = FinalizedExecution(final_status)
    except SQLAlchemyError:
        final_status = RunnerStatus.RETRYABLE
        result = finalize_pipeline_run(
            claim,
            metrics=None,
            status=final_status,
            error_code="DB_UNAVAILABLE",
        )
    except Exception:
        final_status = RunnerStatus.RETRYABLE
        result = finalize_pipeline_run(
            claim,
            metrics=None,
            status=final_status,
            error_code="LOAD_FAILED",
        )
    finally:
        # This output is explicitly dev-only and non-critical; return_state=True
        # absorbs filesystem failures without changing the durable run outcome.
        publish_run_summary(claim.run_id, final_status, metrics, return_state=True)
    return result


def prefect_executor(_engine: Engine, claim: RunClaim) -> FinalizedExecution:
    return weekly_warehouse_client_performance(claim, pipeline_version="engagement-6-phase-6")
