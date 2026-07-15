"""Single server-side derivation for reporting queue and readiness state."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, TypeAlias

QueueState: TypeAlias = Literal["idle", "processing", "queued", "retrying", "stuck", "unavailable"]
WORKER_STALE_AFTER = timedelta(seconds=30)
PROGRESS_STALE_AFTER = timedelta(seconds=120)


@dataclass(frozen=True)
class QueueSignals:
    heartbeat_at: datetime | None
    last_progress_at: datetime | None
    orchestrator_healthy: bool | None
    running_stage: str | None = None
    stage_started_at: datetime | None = None
    latest_status: str | None = None
    latest_next_attempt_at: datetime | None = None
    queued_count: int = 0


def stage_deadline_seconds(stage: str | None) -> int:
    normalized = (stage or "").upper()
    return int(os.environ.get(f"REPORTING_STAGE_TIMEOUT_{normalized}_SECONDS", "300"))


def derive_queue_state(signals: QueueSignals, *, now: datetime) -> QueueState:
    """Derive one truthful state used by both readiness and the public reporting API."""
    if (
        signals.heartbeat_at is None
        or now - signals.heartbeat_at > WORKER_STALE_AFTER
        or signals.orchestrator_healthy is not True
    ):
        return "unavailable"
    if signals.running_stage is not None or signals.stage_started_at is not None:
        if signals.stage_started_at is None:
            return "stuck"
        if now - signals.stage_started_at > timedelta(
            seconds=stage_deadline_seconds(signals.running_stage)
        ):
            return "stuck"
        return "processing"
    if signals.last_progress_at is None or now - signals.last_progress_at > PROGRESS_STALE_AFTER:
        return "stuck"
    if signals.latest_status == "retryable" and signals.latest_next_attempt_at is not None:
        return "retrying"
    if signals.latest_status == "requested" or signals.queued_count > 0:
        return "queued"
    return "idle"
