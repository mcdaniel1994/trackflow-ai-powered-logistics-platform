"""Direct SQL executor for the existing durable reporting-run contract."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Event
from typing import Final, TypeVar

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from .queue import (
    ErrorCode,
    LeaseLostError,
    RunClaim,
    RunMetrics,
    claim_is_owned,
    record_stage,
)
from .retries import is_transient_connectivity_failure, run_with_transient_retries
from .rollups import (
    ROLLUP_PIPELINE_VERSION,
    activate_reconciled_rollups,
    capture_rollup_window,
    compute_hourly_rollups,
    publish_hourly_rollups,
    rollup_cutover_enabled,
)
from .runner import PipelineStageError

logger = logging.getLogger(__name__)

DIRECT_SQL_RETRY_DELAYS_SECONDS: Final = (10.0, 10.0)
T = TypeVar("T")


def _ensure_owned(engine: Engine, claim: RunClaim, abort: Event | None) -> None:
    """Enforce abort and claim-token ownership without relying on Prefect context."""
    if abort is not None and abort.is_set():
        raise LeaseLostError("pipeline run lease is no longer owned")
    if not claim_is_owned(engine, claim):
        raise LeaseLostError("pipeline run lease is no longer owned")


def _begin_stage(
    engine: Engine,
    claim: RunClaim,
    stage: str,
    abort: Event | None,
) -> float:
    """Record every production stage under claim-token CAS."""
    _ensure_owned(engine, claim, abort)
    if not record_stage(engine, claim, stage):
        raise LeaseLostError("pipeline run lease is no longer owned")
    logger.info(
        "reporting_stage_start run_id=%s attempt=%s stage=%s",
        claim.run_id,
        claim.attempt,
        stage,
    )
    return time.monotonic()


def _complete_stage(
    engine: Engine,
    claim: RunClaim,
    stage: str,
    started: float,
    abort: Event | None,
) -> None:
    _ensure_owned(engine, claim, abort)
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    logger.info(
        "reporting_stage_complete run_id=%s attempt=%s stage=%s duration_ms=%s",
        claim.run_id,
        claim.attempt,
        stage,
        duration_ms,
    )


def _run_sql(operation: Callable[[], T]) -> T:
    """Use three total attempts only for the approved connectivity allowlist."""
    return run_with_transient_retries(
        operation,
        delays=DIRECT_SQL_RETRY_DELAYS_SECONDS,
        sleeper=time.sleep,
    )


def _stage_failure(stage: str, exc: Exception) -> PipelineStageError:
    """Translate failures into the existing safe queue-level taxonomy."""
    if is_transient_connectivity_failure(exc):
        return PipelineStageError(
            stage=stage,
            error_code="DB_UNAVAILABLE",
            error_type=type(exc).__name__,
            retryable=True,
        )
    if isinstance(exc, SQLAlchemyError):
        error_code: ErrorCode = (
            "LOAD_FAILED"
            if stage == "load"
            else "EXTRACT_FAILED"
            if stage == "extract"
            else "INTERNAL_FAILED"
        )
        return PipelineStageError(
            stage=stage,
            error_code=error_code,
            error_type=type(exc).__name__,
            retryable=True,
        )
    fallback_error_code: ErrorCode = (
        "LOAD_FAILED" if stage == "load" else "INTERNAL_FAILED"
    )
    if stage == "extract":
        fallback_error_code = "EXTRACT_FAILED"
    return PipelineStageError(
        stage=stage,
        error_code=fallback_error_code,
        error_type=type(exc).__name__,
        retryable=True,
    )


def direct_sql_executor(
    engine: Engine,
    claim: RunClaim,
    abort: Event | None = None,
) -> RunMetrics:
    """Compute and publish rollups without changing queue or lease ownership."""
    extract_started = _begin_stage(engine, claim, "extract", abort)
    try:
        window = _run_sql(lambda: capture_rollup_window(engine, claim))
    except LeaseLostError:
        raise
    except Exception as exc:
        raise _stage_failure("extract", exc) from None
    _complete_stage(engine, claim, "extract", extract_started, abort)

    transform_started = _begin_stage(engine, claim, "transform", abort)
    try:
        rows = _run_sql(lambda: compute_hourly_rollups(engine, window))
    except LeaseLostError:
        raise
    except Exception as exc:
        raise _stage_failure("transform", exc) from None
    _complete_stage(engine, claim, "transform", transform_started, abort)

    load_started = _begin_stage(engine, claim, "load", abort)
    try:
        if rollup_cutover_enabled():
            activation = _run_sql(
                lambda: activate_reconciled_rollups(
                    engine,
                    claim,
                    window,
                    rows=rows,
                    pipeline_version=ROLLUP_PIPELINE_VERSION,
                )
            )
            written = activation.hourly_rows_written
            served_rows = activation.weekly_rows_written
        else:
            written = _run_sql(
                lambda: publish_hourly_rollups(
                    engine,
                    claim,
                    window,
                    rows,
                    pipeline_version=ROLLUP_PIPELINE_VERSION,
                )
            )
            served_rows = written
    except LeaseLostError:
        raise
    except Exception as exc:
        raise _stage_failure("load", exc) from None
    _complete_stage(engine, claim, "load", load_started, abort)

    return RunMetrics(
        rows_extracted=window.rows_scanned,
        rows_transformed=len(rows),
        rows_loaded=served_rows,
        source_watermark=window.source_cutoff_at,
        source_cutoff_at=window.source_cutoff_at,
        rows_scanned=window.rows_scanned,
        rollup_rows_written=written,
    )
