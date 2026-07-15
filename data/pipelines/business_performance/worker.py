"""Long-running reporting worker for the durable queue and Dallas schedule."""

from __future__ import annotations

import logging
import signal
from collections.abc import Callable
from threading import Event, Thread
from types import FrameType

from sqlalchemy import Engine

from .dispatcher import dispatch_tick
from .queue import engine_from_environment, record_worker_heartbeat
from .runner import RunExecutor, run_once

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5.0
HEARTBEAT_INTERVAL_SECONDS = 10.0
DISPATCH_INTERVAL_SECONDS = 60.0


def _safe_failure(operation: str, exc: Exception) -> None:
    """Log only fixed operation names and exception types."""
    logger.error("reporting_worker_operation_failed operation=%s error_type=%s", operation, type(exc).__name__)


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
    background = (
        Thread(
            target=_periodic,
            kwargs={
                "stop": stop,
                "interval_seconds": heartbeat_interval_seconds,
                "operation_name": "heartbeat",
                "operation": lambda: record_worker_heartbeat(engine),
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
                result = run_once(engine, executor)
                if result.run_id is not None:
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


def main() -> None:
    """Run one single-concurrency worker until SIGTERM or SIGINT."""
    from .flows import prefect_executor

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    stop = Event()
    signal.signal(signal.SIGTERM, _stop(stop))
    signal.signal(signal.SIGINT, _stop(stop))
    engine = engine_from_environment()
    try:
        run_worker(engine, prefect_executor, stop=stop)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
