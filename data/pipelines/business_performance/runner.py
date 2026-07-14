"""One-shot durable queue runner with leases and defense-in-depth locking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import Engine

from .locks import REPORTING_PIPELINE_LOCK_KEY, advisory_lock
from .queue import (
    ErrorCode,
    LeaseLostError,
    RunClaim,
    RunMetrics,
    claim_next,
    finalize_failure,
    finalize_success,
    heartbeat,
    release_retryable,
)

RunExecutor = Callable[[Engine, RunClaim], RunMetrics]


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


class TransientRunError(RuntimeError):
    def __init__(self, error_code: ErrorCode) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class PermanentRunError(RuntimeError):
    def __init__(self, error_code: ErrorCode) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class RunnerNotConfiguredError(RuntimeError):
    """Raised until the Phase 6 ETL executor is wired to the one-shot runner."""


def run_once(
    engine: Engine,
    executor: RunExecutor,
    *,
    lock_key: int = REPORTING_PIPELINE_LOCK_KEY,
) -> RunnerResult:
    """Claim at most one request and reconcile it through a token-verified transition."""
    claim = claim_next(engine)
    if claim is None:
        return RunnerResult(RunnerStatus.IDLE)
    run_id = str(claim.run_id)

    with advisory_lock(engine, lock_key) as acquired:
        if not acquired:
            transitioned = release_retryable(engine, claim, "LOCK_UNAVAILABLE")
            return RunnerResult(RunnerStatus.RETRYABLE if transitioned else RunnerStatus.LEASE_LOST, run_id)
        if not heartbeat(engine, claim):
            return RunnerResult(RunnerStatus.LEASE_LOST, run_id)
        try:
            metrics = executor(engine, claim)
            if not heartbeat(engine, claim):
                raise LeaseLostError("pipeline run lease is no longer owned")
        except LeaseLostError:
            return RunnerResult(RunnerStatus.LEASE_LOST, run_id)
        except PermanentRunError as exc:
            transitioned = finalize_failure(engine, claim, exc.error_code)
            return RunnerResult(RunnerStatus.FAILED if transitioned else RunnerStatus.LEASE_LOST, run_id)
        except TransientRunError as exc:
            transitioned = release_retryable(engine, claim, exc.error_code)
            return RunnerResult(RunnerStatus.RETRYABLE if transitioned else RunnerStatus.LEASE_LOST, run_id)
        except Exception:
            # Persist only a fixed failure class; payloads, SQL, credentials, and
            # stack traces never enter the durable audit row.
            transitioned = release_retryable(engine, claim, "EXTRACT_FAILED")
            return RunnerResult(RunnerStatus.RETRYABLE if transitioned else RunnerStatus.LEASE_LOST, run_id)

        transitioned = finalize_success(engine, claim, metrics)
        return RunnerResult(RunnerStatus.SUCCEEDED if transitioned else RunnerStatus.LEASE_LOST, run_id)


def main() -> None:
    """Refuse to consume durable work until the Phase 6 ETL executor exists."""
    raise RunnerNotConfiguredError("business-performance executor is introduced in Phase 6")


if __name__ == "__main__":
    main()
