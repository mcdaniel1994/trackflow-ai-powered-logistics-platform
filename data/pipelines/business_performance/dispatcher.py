"""America/Chicago scheduling tick for the durable reporting queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import Engine

from .queue import engine_from_environment, enqueue_scheduled, recover_stale_runs

DALLAS_TIMEZONE = ZoneInfo("America/Chicago")
REFRESH_TIMES = (time(hour=7), time(hour=19))


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
    """Sweep stale leases, then idempotently enqueue the latest 12-hour slot."""
    tick_at = now or datetime.now(UTC)
    local = dallas_business_time(tick_at)
    recovered = recover_stale_runs(engine, now=tick_at)
    created = False
    refresh_times = REFRESH_TIMES
    eligible = [
        refresh_time
        for refresh_time in refresh_times
        if local.time().replace(tzinfo=None) >= refresh_time
    ]
    if eligible:
        refresh_time = eligible[-1]
        scheduled_local = datetime.combine(
            local.date(),
            refresh_time,
            tzinfo=DALLAS_TIMEZONE,
        )
        # Keep the legacy business-date identity on the morning slot so the
        # prior image can run against this additive schema. The evening slot is
        # uniquely identified by scheduled_for and leaves the legacy date NULL.
        business_date = local.date() if refresh_time == refresh_times[0] else None
        created = (
            enqueue_scheduled(
                engine,
                business_date,
                scheduled_for=scheduled_local.astimezone(UTC),
                now=tick_at,
            )
            is not None
        )
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
