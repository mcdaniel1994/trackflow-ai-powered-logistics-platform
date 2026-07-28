"""Enforce age and total-byte limits on host-persisted reporting logs."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_RETENTION_DAYS = 14
DEFAULT_TOTAL_BYTES = 250 * 1024 * 1024


def prune_once(
    *,
    now: datetime | None = None,
    log_path: str | None = None,
    retention_days: int | None = None,
    total_bytes: int | None = None,
) -> dict[str, int]:
    raw_path = (log_path if log_path is not None else os.environ.get("REPORTING_LOG_PATH", "")).strip()
    if not raw_path:
        return {"files_deleted": 0, "bytes_deleted": 0}
    path = Path(raw_path)
    directory = path.parent
    if not directory.exists():
        return {"files_deleted": 0, "bytes_deleted": 0}

    keep_days = retention_days or int(
        os.environ.get("REPORTING_LOG_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)
    )
    ceiling = total_bytes or int(
        os.environ.get("REPORTING_LOG_TOTAL_BYTES", DEFAULT_TOTAL_BYTES)
    )
    cutoff = (now or datetime.now(UTC)) - timedelta(days=keep_days)
    candidates = [
        item
        for item in directory.glob(f"{path.name}*")
        if item.is_file() and not item.is_symlink()
    ]
    deleted_files = 0
    deleted_bytes = 0

    for item in list(candidates):
        stat = item.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        if modified >= cutoff:
            continue
        item.unlink()
        deleted_files += 1
        deleted_bytes += stat.st_size
        candidates.remove(item)

    remaining = sorted(
        ((item.stat().st_mtime, item.stat().st_size, item) for item in candidates),
        key=lambda value: value[0],
    )
    current_bytes = sum(size for _, size, _ in remaining)
    for _, size, item in remaining:
        if current_bytes <= ceiling:
            break
        item.unlink()
        current_bytes -= size
        deleted_files += 1
        deleted_bytes += size
    return {"files_deleted": deleted_files, "bytes_deleted": deleted_bytes}
