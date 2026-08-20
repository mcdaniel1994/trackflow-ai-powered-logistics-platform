"""Long-running reporting worker for the durable queue and Dallas schedule."""

from __future__ import annotations

import logging
import os
import signal
from collections.abc import Callable
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event, Lock, Thread
from types import FrameType

from sqlalchemy import Engine

from .dispatcher import dispatch_tick
from .queue import claim_next, engine_from_environment, record_worker_heartbeat, utc_now
from .runner import RunExecutor, execute_claim_with_renewal, finalize_claim

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5.0
HEARTBEAT_INTERVAL_SECONDS = 10.0
DISPATCH_INTERVAL_SECONDS = 60.0
DEFAULT_RUN_TIMEOUT_SECONDS = 1800.0
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 9
COMPUTATION_FEATURE_FLAG = "REPORTING_COMPUTATION_ENABLED"


def computation_enabled() -> bool:
    """Return the production computation kill switch; defaults enabled."""
    return os.environ.get(COMPUTATION_FEATURE_FLAG, "true").strip().lower() == "true"


def _safe_failure(operation: str, exc: Exception) -> None:
    """Log only fixed operation names and exception types."""
    logger.error("reporting_worker_operation_failed operation=%s error_type=%s", operation, type(exc).__name__)


class _Liveness:
    """Liveness shared by the poll loop and the heartbeat thread, written once per change.

    The poll loop used to write this singleton row on every 5 s iteration while the
    heartbeat thread wrote the same row every 10 s. The thread alone already carries
    worker liveness — it keeps beating while the loop is blocked inside a run — so the
    per-poll write was pure duplication, and in production it dominated the database's
    write volume.

    The loop now records its observation in memory and writes only when
    ``orchestrator_healthy`` actually changes, so a health transition still reaches the
    status contract immediately rather than waiting for the next beat. Steady state
    costs no extra writes. The spec-frozen 10 s heartbeat interval is unchanged.

    Both threads touch this state, so every read and write is taken under the lock.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_progress_at: datetime | None = None
        self._orchestrator_healthy: bool | None = None
        self._written_orchestrator_healthy: bool | None = None

    def observe(
        self, engine: Engine, *, last_progress_at: datetime, orchestrator_healthy: bool
    ) -> None:
        """Record progress, writing through only on an orchestrator-health transition."""
        with self._lock:
            self._last_progress_at = last_progress_at
            self._orchestrator_healthy = orchestrator_healthy
            changed = orchestrator_healthy != self._written_orchestrator_healthy
        if changed:
            self.write(engine)

    def write(self, engine: Engine) -> None:
        """Persist the newest observation; None values preserve the stored row (COALESCE)."""
        with self._lock:
            last_progress_at = self._last_progress_at
            orchestrator_healthy = self._orchestrator_healthy
            self._written_orchestrator_healthy = orchestrator_healthy
        record_worker_heartbeat(
            engine,
            last_progress_at=last_progress_at,
            orchestrator_healthy=orchestrator_healthy,
        )


def _periodic(
    stop: Event,
    *,
    interval_seconds: float,
    operation_name: str,
    operation: Callable[[], object],
) -> None:
    """Run immediately and then at a fixed interval until shutdown."""
    while not stop.is_set():
        try:
            operation()
        except Exception as exc:
            _safe_failure(operation_name, exc)
        stop.wait(interval_seconds)


def _run_watchdog(done: Event, timeout_seconds: float, run_id: str, attempt: int) -> None:
    if done.wait(timeout_seconds):
        return
    logger.critical(
        "reporting_run_timeout run_id=%s attempt=%s stage=orchestration",
        run_id,
        attempt,
    )
    for handler in logging.getLogger().handlers:
        handler.flush()
    os._exit(1)


def run_worker(
    engine: Engine,
    executor: RunExecutor,
    *,
    stop: Event,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
    heartbeat_interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
    dispatch_interval_seconds: float = DISPATCH_INTERVAL_SECONDS,
) -> None:
    """Poll serially while heartbeat and scheduling remain responsive."""
    liveness = _Liveness()
    background = (
        Thread(
            target=_periodic,
            kwargs={
                "stop": stop,
                "interval_seconds": heartbeat_interval_seconds,
                "operation_name": "heartbeat",
                "operation": lambda: liveness.write(engine),
            },
            name="reporting-heartbeat",
        ),
        Thread(
            target=_periodic,
            kwargs={
                "stop": stop,
                "interval_seconds": dispatch_interval_seconds,
                "operation_name": "dispatch",
                "operation": lambda: dispatch_tick(engine),
            },
            name="reporting-dispatcher",
        ),
    )
    for thread in background:
        thread.start()

    logger.info("reporting_worker_started")
    try:
        while not stop.is_set():
            try:
                # Direct SQL executes in this process, so the worker is its own
                # orchestrator: a beating worker is a healthy one. Steady state is
                # recorded in memory and persisted by the heartbeat thread; only a
                # transition writes through from here.
                liveness.observe(
                    engine, last_progress_at=utc_now(), orchestrator_healthy=True
                )
                if not computation_enabled():
                    stop.wait(poll_interval_seconds)
                    continue
                claim = claim_next(engine)
                if claim is not None:
                    done = Event()
                    timeout_seconds = float(
                        os.environ.get("REPORTING_RUN_TIMEOUT_SECONDS", DEFAULT_RUN_TIMEOUT_SECONDS)
                    )
                    watchdog = Thread(
                        target=_run_watchdog,
                        args=(done, timeout_seconds, str(claim.run_id), claim.attempt),
                        name="reporting-run-watchdog",
                        daemon=True,
                    )
                    watchdog.start()
                    try:
                        outcome = execute_claim_with_renewal(engine, executor, claim)
                        result = finalize_claim(engine, claim, outcome)
                    finally:
                        done.set()
                        watchdog.join(timeout=1)
                    logger.info("reporting_worker_run_complete run_id=%s status=%s", result.run_id, result.status)
            except Exception as exc:
                _safe_failure("poll", exc)
            stop.wait(poll_interval_seconds)
    finally:
        stop.set()
        for thread in background:
            thread.join(timeout=max(heartbeat_interval_seconds, dispatch_interval_seconds) + 1)
        logger.info("reporting_worker_stopped")


def _stop(stop: Event) -> Callable[[int, FrameType | None], None]:
    def handler(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    return handler


def _configure_persisted_log() -> None:
    """Add a bounded host-mounted log without replacing stdout diagnostics."""
    raw_path = os.environ.get("REPORTING_LOG_PATH", "").strip()
    if not raw_path:
        return
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    path.parent.chmod(0o750)
    handler = RotatingFileHandler(
        path,
        maxBytes=int(os.environ.get("REPORTING_LOG_MAX_BYTES", DEFAULT_LOG_MAX_BYTES)),
        backupCount=int(os.environ.get("REPORTING_LOG_BACKUP_COUNT", DEFAULT_LOG_BACKUP_COUNT)),
        encoding="utf-8",
    )
    path.chmod(0o640)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(handler)


def main() -> None:
    """Run one single-concurrency worker until SIGTERM or SIGINT."""
    from .executor_selection import executor_from_environment

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    _configure_persisted_log()

    # Direct SQL runs inside this container against PostgreSQL only: there is no
    # external orchestrator to probe, so the executor allowlist is the whole
    # startup contract and it still fails closed on an unrecognised value.
    try:
        executor_name, executor = executor_from_environment()
    except ValueError:
        logger.critical("reporting_worker_startup_guard=failed reason=unsupported_executor")
        raise SystemExit(1) from None
    logger.info(
        "reporting_worker_startup_guard=complete executor=%s",
        executor_name,
    )

    stop = Event()
    signal.signal(signal.SIGTERM, _stop(stop))
    signal.signal(signal.SIGINT, _stop(stop))
    engine = engine_from_environment()
    try:
        run_worker(engine, executor, stop=stop)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
