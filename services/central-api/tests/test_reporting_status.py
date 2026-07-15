"""Shared reporting queue-state derivation matrix."""

from datetime import UTC, datetime, timedelta

import pytest

from central_api.domains.reporting.status import QueueSignals, derive_queue_state

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
        ({"last_progress_at": NOW - timedelta(minutes=3), "queued_count": 1}, "stuck"),
        ({"orchestrator_healthy": False, "queued_count": 1}, "unavailable"),
        ({"heartbeat_at": NOW - timedelta(seconds=31)}, "unavailable"),
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
