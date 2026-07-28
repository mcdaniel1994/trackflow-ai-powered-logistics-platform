"""Shared reporting queue-state derivation matrix."""

from datetime import UTC, datetime, timedelta

import pytest
from pipelines.business_performance.queue import DEFAULT_LEASE_SECONDS
from pipelines.business_performance.runner import DEFAULT_LEASE_RENEWAL_SECONDS
from pipelines.business_performance.worker import (
    DEFAULT_RUN_TIMEOUT_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
)

from central_api.domains.reporting.status import (
    PROGRESS_STALE_AFTER,
    WORKER_STALE_AFTER,
    QueueSignals,
    derive_queue_state,
    stage_deadline_seconds,
)

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, "idle"),
        ({"latest_status": "requested", "queued_count": 1}, "queued"),
        (
            {
                "latest_status": "retryable",
                "latest_next_attempt_at": NOW + timedelta(minutes=1),
            },
            "retrying",
        ),
        ({"running_stage": "extract", "stage_started_at": NOW - timedelta(seconds=10)}, "processing"),
        ({"running_stage": "transform", "stage_started_at": NOW - timedelta(minutes=6)}, "stuck"),
        ({"last_progress_at": NOW - timedelta(seconds=181), "queued_count": 1}, "stuck"),
        ({"orchestrator_healthy": False, "queued_count": 1}, "unavailable"),
        ({"heartbeat_at": NOW - timedelta(seconds=61)}, "unavailable"),
    ],
)
def test_queue_state_matrix(changes: dict[str, object], expected: str) -> None:
    values: dict[str, object] = {
        "heartbeat_at": NOW - timedelta(seconds=5),
        "last_progress_at": NOW - timedelta(seconds=5),
        "orchestrator_healthy": True,
    }
    values.update(changes)
    assert derive_queue_state(QueueSignals(**values), now=NOW) == expected  # type: ignore[arg-type]


def test_reporting_timeout_ordering_is_coherent(monkeypatch: pytest.MonkeyPatch) -> None:
    for stage in ("EXTRACT", "TRANSFORM", "LOAD"):
        monkeypatch.delenv(f"REPORTING_STAGE_TIMEOUT_{stage}_SECONDS", raising=False)
        assert stage_deadline_seconds(stage.lower()) == 300
    assert 300 < DEFAULT_LEASE_SECONDS < DEFAULT_RUN_TIMEOUT_SECONDS
    assert DEFAULT_LEASE_SECONDS / DEFAULT_LEASE_RENEWAL_SECONDS == 15
    assert WORKER_STALE_AFTER.total_seconds() / HEARTBEAT_INTERVAL_SECONDS == 6
    assert PROGRESS_STALE_AFTER.total_seconds() == 180
