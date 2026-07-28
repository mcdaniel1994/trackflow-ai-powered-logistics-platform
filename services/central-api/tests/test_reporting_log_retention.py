"""Bounded reporting-log retention owned by the maintenance worker."""

from datetime import UTC, datetime
from os import utime

from scripts.prune_reporting_logs import prune_once


def test_reporting_log_retention_enforces_age_and_total_bytes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    active = tmp_path / "worker.log"
    old = tmp_path / "worker.log.2"
    oldest = tmp_path / "worker.log.3"
    unrelated = tmp_path / "other.log"
    for path, content in (
        (active, b"a" * 8),
        (old, b"b" * 8),
        (oldest, b"c" * 8),
        (unrelated, b"private"),
    ):
        path.write_bytes(content)
    utime(oldest, (1, 1))
    utime(old, (2, 2))

    result = prune_once(
        now=datetime(2026, 7, 28, tzinfo=UTC),
        log_path=str(active),
        retention_days=10_000,
        total_bytes=10,
    )

    assert result == {"files_deleted": 2, "bytes_deleted": 16}
    assert active.exists()
    assert unrelated.exists()
