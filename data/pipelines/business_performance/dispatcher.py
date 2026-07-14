"""America/Chicago scheduling tick for the durable reporting queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import Engine

from .queue import engine_from_environment, enqueue_scheduled, recover_stale_runs

DALLAS_TIMEZONE = ZoneInfo("America/Chicago")
DAILY_REFRESH_TIME = time(hour=7)


@dataclass(frozen=True)
class DispatchResult:
    business_date: date
    scheduled_run_created: bool
    stale_runs_recovered: int


def dallas_business_time(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("dispatcher clock must be timezone-aware")
    return now.astimezone(DALLAS_TIMEZONE)


def dispatch_tick(engine: Engine, *, now: datetime | None = None) -> DispatchResult:
    """Sweep stale leases, then enqueue today's request once local 07:00 has passed."""
    tick_at = now or datetime.now(UTC)
    local = dallas_business_time(tick_at)
    recovered = recover_stale_runs(engine, now=tick_at)
    created = False
    if local.time().replace(tzinfo=None) >= DAILY_REFRESH_TIME:
        created = enqueue_scheduled(engine, local.date(), now=tick_at) is not None
    return DispatchResult(
        business_date=local.date(),
        scheduled_run_created=created,
        stale_runs_recovered=recovered,
    )


def main() -> None:
    engine = engine_from_environment()
    try:
        dispatch_tick(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
