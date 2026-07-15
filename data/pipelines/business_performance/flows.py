"""Prefect-as-library ETL flows for weekly warehouse/client performance."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from threading import Event
from typing import Final, cast
from uuid import UUID

import httpx
from prefect import flow, task
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterName
from prefect.context import FlowRunContext, get_run_context
from prefect.exceptions import MissingContextError, PrefectHTTPStatusError
from prefect.states import Crashed
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
    prefect_result_storage_from_environment,
    prefect_transformation_cache_key,
    transform_with_cache,
)
from .queue import (
    DEFAULT_RECOMPUTE_WEEKS,
    ErrorCode,
    LeaseLostError,
    RunClaim,
    RunMetrics,
    claim_is_owned,
    engine_from_environment,
    record_prefect_flow_run,
    record_stage,
    verify_claim_for_publication,
)
from .runner import PipelineStageError

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
def publish_run_summary(run_id: UUID, metrics: RunMetrics) -> None:
    if os.environ.get("REPORTING_EVAL_OUTPUT_ENABLED", "false").lower() != "true":
        return
    output_dir = Path(__file__).resolve().parents[2] / "eval" / "business_performance"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": str(run_id),
        "status": "succeeded",
        "rows_extracted": metrics.rows_extracted,
        "rows_transformed": metrics.rows_transformed,
        "rows_loaded": metrics.rows_loaded,
    }
    (output_dir / f"{run_id}.json").write_text(json.dumps(payload, sort_keys=True) + "\n")


def _stage_failure(stage: str, exc: Exception) -> PipelineStageError:
    if isinstance(exc, (TransformError, CacheConfigurationError)):
        return PipelineStageError(
            stage=stage,
            error_code="VALIDATE_FAILED",
            error_type=type(exc).__name__,
            retryable=False,
        )
    if isinstance(exc, SQLAlchemyError):
        return PipelineStageError(
            stage=stage,
            error_code="DB_UNAVAILABLE",
            error_type=type(exc).__name__,
            retryable=True,
        )
    if isinstance(exc, (PrefectHTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return PipelineStageError(
            stage=stage,
            error_code="ORCHESTRATION_FAILED",
            error_type=type(exc).__name__,
            retryable=True,
        )
    error_code: ErrorCode = "EXTRACT_FAILED" if stage == "extract" else "INTERNAL_FAILED"
    if stage == "load":
        error_code = "LOAD_FAILED"
    return PipelineStageError(
        stage=stage,
        error_code=error_code,
        error_type=type(exc).__name__,
        retryable=True,
    )


@flow(name="weekly_warehouse_client_performance", persist_result=False)
def weekly_warehouse_client_performance(claim: RunClaim, pipeline_version: str) -> RunMetrics:
    """Run ETL stages; the durable runner owns queue finalization."""
    try:
        context = get_run_context()
        if not isinstance(context, FlowRunContext) or context.flow_run is None:
            raise MissingContextError("flow context required")
        flow_run_id = UUID(str(context.flow_run.id))
    except MissingContextError:
        # Direct `.fn` calls are supported only for pure unit tests; the production
        # executor always enters through Prefect and therefore always performs CAS.
        flow_run_id = None
    if flow_run_id is not None:
        engine = _engine()
        try:
            if not record_prefect_flow_run(engine, claim, flow_run_id):
                raise LeaseLostError("pipeline run lease is no longer owned")
        finally:
            engine.dispose()

    _begin_stage(claim, "extract", enforce=flow_run_id is not None)
    try:
        extracted = extract_warehouse_client_activity(claim.target_weeks)
    except LeaseLostError:
        raise
    except Exception as exc:
        raise _stage_failure("extract", exc) from None

    _begin_stage(claim, "transform", enforce=flow_run_id is not None)
    try:
        transform_flow = transform_weekly_performance
        recovery_storage = prefect_result_storage_from_environment()
        if recovery_storage is not None:
            transform_flow = transform_flow.with_options(
                persist_result=True,
                result_storage=recovery_storage,
            )
        transformed = transform_flow(
            extracted,
            claim,
            last_reset_at=_last_reset_at(),
            pipeline_version=pipeline_version,
        )
    except LeaseLostError:
        raise
    except Exception as exc:
        raise _stage_failure("transform", exc) from None

    _begin_stage(claim, "load", enforce=flow_run_id is not None)
    try:
        loaded = load_weekly_performance_report(transformed.rows, claim)
    except LeaseLostError:
        raise
    except Exception as exc:
        raise _stage_failure("load", exc) from None

    metrics = RunMetrics(
        rows_extracted=extracted.rows_extracted,
        rows_transformed=len(transformed.rows),
        rows_loaded=loaded.rows_loaded,
        source_watermark=extracted.source_watermark,
    )
    # Dev-only output is non-critical and cannot change the durable outcome.
    publish_run_summary(claim.run_id, metrics, return_state=True)
    return metrics


def _begin_stage(claim: RunClaim, stage: str, *, enforce: bool) -> None:
    if not enforce:
        return
    engine = _engine()
    try:
        if not claim_is_owned(engine, claim) or not record_stage(engine, claim, stage):
            raise LeaseLostError("pipeline run lease is no longer owned")
    finally:
        engine.dispose()


def _flow_run_name(claim: RunClaim) -> str:
    return f"business-performance-{claim.run_id}-attempt-{claim.attempt}"


def prefect_executor(_engine: Engine, claim: RunClaim, abort: Event | None = None) -> RunMetrics:
    if abort is not None and abort.is_set():
        raise LeaseLostError("pipeline run lease is no longer owned")
    configured = weekly_warehouse_client_performance.with_options(flow_run_name=_flow_run_name(claim))
    return configured(claim, pipeline_version="engagement-6-phase-6")


async def _close_orphan(flow_run_id: UUID | None, deterministic_name: str) -> bool:
    async with get_client() as client:
        candidates = []
        if flow_run_id is not None:
            try:
                candidates = [await client.read_flow_run(flow_run_id)]
            except Exception:
                candidates = []
        if not candidates:
            candidates = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(name=FlowRunFilterName(any_=[deterministic_name])),
                limit=1,
            )
        if not candidates or candidates[0].state is None or candidates[0].state.is_final():
            return False
        await client.set_flow_run_state(candidates[0].id, Crashed(message="worker restart reconciliation"), force=True)
        return True


def reconcile_orphaned_flow_runs(engine: Engine) -> int:
    """Close Prefect runs left non-terminal by a prior worker process."""
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, attempt, prefect_flow_run_id FROM reporting.pipeline_runs "
                "WHERE pipeline_name = 'business_performance' AND status = 'running'"
            )
        ).mappings().all()
    reconciled = 0
    for row in rows:
        run_id = UUID(str(row["id"]))
        flow_run_id = UUID(str(row["prefect_flow_run_id"])) if row["prefect_flow_run_id"] else None
        name = f"business-performance-{run_id}-attempt-{int(row['attempt'])}"
        try:
            reconciled += int(asyncio.run(_close_orphan(flow_run_id, name)))
        except (PrefectHTTPStatusError, httpx.TransportError, httpx.TimeoutException) as exc:
            logging.getLogger(__name__).warning(
                "reporting_orphan_reconciliation_deferred error_type=%s", type(exc).__name__
            )
    return reconciled
