"""One-shot durable queue runner with leases and defense-in-depth locking."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from inspect import signature
from threading import Event, Thread

from sqlalchemy import Engine

from .locks import REPORTING_PIPELINE_LOCK_KEY, advisory_lock
from .queue import (
    ErrorCode,
    LeaseLostError,
    RunClaim,
    RunMetrics,
    claim_next,
    engine_from_environment,
    finalize_failure,
    finalize_success,
    heartbeat,
    release_retryable,
)

logger = logging.getLogger(__name__)


class RunnerStatus(StrEnum):
    IDLE = "idle"
    SUCCEEDED = "succeeded"
    RETRYABLE = "retryable"
    FAILED = "failed"
    LEASE_LOST = "lease_lost"


@dataclass(frozen=True)
class RunnerResult:
    status: RunnerStatus
    run_id: str | None = None


RunExecutor = Callable[..., RunMetrics]


@dataclass(frozen=True)
class ClaimOutcome:
    status: RunnerStatus
    metrics: RunMetrics | None = None
    error_code: ErrorCode | None = None


class TransientRunError(RuntimeError):
    def __init__(self, error_code: ErrorCode) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class PermanentRunError(RuntimeError):
    def __init__(self, error_code: ErrorCode) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class PipelineStageError(RuntimeError):
    """Safe cross-boundary failure metadata without exception messages or payloads."""

    def __init__(
        self,
        *,
        stage: str,
        error_code: ErrorCode,
        error_type: str,
        retryable: bool,
    ) -> None:
        super().__init__("pipeline stage failed")
        self.stage = stage
        self.error_code = error_code
        self.error_type = error_type
        self.retryable = retryable


def _invoke_executor(executor: RunExecutor, engine: Engine, claim: RunClaim, abort: Event) -> RunMetrics:
    """Keep older two-argument callers compatible while the worker passes abort state."""
    if len(signature(executor).parameters) >= 3:
        return executor(engine, claim, abort)
    return executor(engine, claim)


def _renew_claim(
    engine: Engine,
    claim: RunClaim,
    *,
    stop: Event,
    abort: Event,
    interval_seconds: float,
) -> None:
    """Renew ownership independently from stage progress; CAS loss requests abort."""
    while not stop.wait(interval_seconds):
        try:
            if not heartbeat(engine, claim):
                abort.set()
                return
        except Exception as exc:
            logger.error("reporting_lease_renewal_failed error_type=%s", type(exc).__name__)
            abort.set()
            return


def execute_claim_with_renewal(
    engine: Engine,
    executor: RunExecutor,
    claim: RunClaim,
    *,
    lock_key: int = REPORTING_PIPELINE_LOCK_KEY,
) -> ClaimOutcome:
    """Execute one already-owned claim while a separate thread renews only its lease."""
    run_id = str(claim.run_id)
    with advisory_lock(engine, lock_key) as acquired:
        if not acquired:
            return ClaimOutcome(RunnerStatus.RETRYABLE, error_code="LOCK_UNAVAILABLE")
        if not heartbeat(engine, claim):
            return ClaimOutcome(RunnerStatus.LEASE_LOST)

        stop = Event()
        abort = Event()
        interval = float(os.environ.get("REPORTING_HEARTBEAT_SECONDS", "60"))
        renewer = Thread(
            target=_renew_claim,
            kwargs={
                "engine": engine,
                "claim": claim,
                "stop": stop,
                "abort": abort,
                "interval_seconds": interval,
            },
            name=f"reporting-lease-{run_id}",
            daemon=True,
        )
        renewer.start()
        try:
            metrics = _invoke_executor(executor, engine, claim, abort)
            if abort.is_set() or not heartbeat(engine, claim):
                raise LeaseLostError("pipeline run lease is no longer owned")
        except LeaseLostError:
            return ClaimOutcome(RunnerStatus.LEASE_LOST)
        except PipelineStageError as exc:
            logger.error(
                "reporting_pipeline_failure run_id=%s attempt=%s stage=%s error_code=%s error_type=%s",
                run_id,
                claim.attempt,
                exc.stage,
                exc.error_code,
                exc.error_type,
            )
            return ClaimOutcome(
                RunnerStatus.RETRYABLE if exc.retryable else RunnerStatus.FAILED,
                error_code=exc.error_code,
            )
        except PermanentRunError as exc:
            return ClaimOutcome(RunnerStatus.FAILED, error_code=exc.error_code)
        except TransientRunError as exc:
            return ClaimOutcome(RunnerStatus.RETRYABLE, error_code=exc.error_code)
        except Exception as exc:
            # Persist only a fixed failure class; payloads, SQL, credentials, and
            # stack traces never enter the durable audit row.
            logger.error(
                "reporting_pipeline_failure run_id=%s attempt=%s stage=orchestration "
                "error_code=INTERNAL_FAILED error_type=%s",
                run_id,
                claim.attempt,
                type(exc).__name__,
            )
            return ClaimOutcome(RunnerStatus.RETRYABLE, error_code="INTERNAL_FAILED")
        finally:
            stop.set()
            renewer.join(timeout=max(1.0, interval + 1.0))

        return ClaimOutcome(RunnerStatus.SUCCEEDED, metrics=metrics)


def finalize_claim(engine: Engine, claim: RunClaim, outcome: ClaimOutcome) -> RunnerResult:
    """Apply one token-CAS final transition after execution releases the advisory lock."""
    run_id = str(claim.run_id)
    if outcome.status == RunnerStatus.LEASE_LOST:
        return RunnerResult(RunnerStatus.LEASE_LOST, run_id)
    if outcome.status == RunnerStatus.SUCCEEDED and outcome.metrics is not None:
        transitioned = finalize_success(engine, claim, outcome.metrics)
    elif outcome.status == RunnerStatus.FAILED and outcome.error_code is not None:
        transitioned = finalize_failure(engine, claim, outcome.error_code)
    elif outcome.status == RunnerStatus.RETRYABLE and outcome.error_code is not None:
        transitioned = release_retryable(engine, claim, outcome.error_code)
    else:
        raise RuntimeError("invalid claim outcome")
    return RunnerResult(outcome.status if transitioned else RunnerStatus.LEASE_LOST, run_id)


def run_once(
    engine: Engine,
    executor: RunExecutor,
    *,
    lock_key: int = REPORTING_PIPELINE_LOCK_KEY,
) -> RunnerResult:
    """Thin compatible composition of claim, execution-with-renewal, and finalization."""
    claim = claim_next(engine)
    if claim is None:
        return RunnerResult(RunnerStatus.IDLE)
    outcome = execute_claim_with_renewal(engine, executor, claim, lock_key=lock_key)
    return finalize_claim(engine, claim, outcome)


def main() -> None:
    """Claim and execute at most one durable request through the Prefect flow."""
    from .flows import prefect_executor

    engine = engine_from_environment()
    try:
        run_once(engine, prefect_executor)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
