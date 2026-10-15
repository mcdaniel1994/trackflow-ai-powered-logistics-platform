"""Prevent topology edits from silently restoring the production connection outage."""

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("filename", ["compose.yaml", "compose.coolify.yaml"])
def test_runtime_connection_budget_leaves_two_session_slots(filename: str) -> None:
    source = (ROOT / filename).read_text()
    expected = {"central-api": (3, 0), "operations-feed": (2, 1),
                "reporting-worker": (2, 3), "maintenance-worker": (1, 0)}
    total = 1  # The RFP checkpointer's separate process-owned pool.
    for service, limits in expected.items():
        block = re.search(rf"(?ms)^  {service}:\n(.*?)(?=^  [a-z][a-z-]*:|\Z)", source)
        assert block is not None
        environment = block[1]
        size = re.search(r'^      DATABASE_POOL_SIZE: "(\d+)"$', environment, re.M)
        overflow = re.search(r'^      DATABASE_MAX_OVERFLOW: "(\d+)"$', environment, re.M)
        assert size and overflow
        actual = (int(size[1]), int(overflow[1]))
        assert actual == limits
        assert 'DATABASE_POOL_TIMEOUT_SECONDS: "5"' in environment
        assert "replicas: 1" in environment
        total += sum(actual)
    assert total == 13
    assert 15 - total == 2
    dockerfile = (ROOT / "docker/central-api.Dockerfile").read_text()
    assert '"--workers", "1"' in dockerfile
