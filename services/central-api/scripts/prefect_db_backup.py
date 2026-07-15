"""Daily encrypted-in-transit Prefect PostgreSQL dumps to private R2 storage."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import FrameType
from typing import Any, Final, Protocol

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]

logger = logging.getLogger("prefect_db_backup")
BACKUP_PREFIX: Final = "prefect-backups/"
BACKUP_INTERVAL_SECONDS: Final = 24 * 60 * 60.0


class BackupStore(Protocol):
    def upload_file(self, Filename: str, Bucket: str, Key: str) -> object: ...

    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict[str, Any]: ...

    def delete_objects(self, *, Bucket: str, Delete: dict[str, Any]) -> object: ...


@dataclass(frozen=True)
class BackupConfig:
    bucket: str
    endpoint: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    retention_days: int = 7
    disk_warning_mb: int = 1024

    @classmethod
    def from_environment(cls) -> BackupConfig | None:
        names = (
            "PREFECT_BACKUP_R2_BUCKET",
            "PREFECT_BACKUP_R2_ENDPOINT",
            "PREFECT_BACKUP_R2_ACCESS_KEY_ID",
            "PREFECT_BACKUP_R2_SECRET_ACCESS_KEY",
        )
        values = {name: os.environ.get(name, "").strip() for name in names}
        if not any(values.values()):
            return None
        if not all(values.values()):
            raise ValueError("PREFECT_BACKUP_R2 configuration must be complete or absent")
        retention_days = int(os.environ.get("PREFECT_BACKUP_RETENTION_DAYS", "7"))
        disk_warning_mb = int(os.environ.get("PREFECT_DB_DISK_WARNING_MB", "1024"))
        if retention_days < 1 or disk_warning_mb < 1:
            raise ValueError("Prefect backup retention and disk warning must be positive")
        return cls(
            bucket=values["PREFECT_BACKUP_R2_BUCKET"],
            endpoint=values["PREFECT_BACKUP_R2_ENDPOINT"],
            access_key_id=values["PREFECT_BACKUP_R2_ACCESS_KEY_ID"],
            secret_access_key=values["PREFECT_BACKUP_R2_SECRET_ACCESS_KEY"],
            retention_days=retention_days,
            disk_warning_mb=disk_warning_mb,
        )


def _store(config: BackupConfig) -> BackupStore:
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name="auto",
        config=Config(connect_timeout=10, read_timeout=60, retries={"max_attempts": 2, "mode": "standard"}),
    )


def _database_size_mb(run: Callable[..., subprocess.CompletedProcess[str]]) -> int:
    result = run(
        ["psql", "-XAt", "-c", "SELECT pg_database_size(current_database())"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return int(result.stdout.strip()) // (1024 * 1024)


def _prune_old_backups(store: BackupStore, config: BackupConfig, *, now: datetime) -> int:
    response = store.list_objects_v2(Bucket=config.bucket, Prefix=BACKUP_PREFIX)
    cutoff = now - timedelta(days=config.retention_days)
    keys = [
        {"Key": item["Key"]}
        for item in response.get("Contents", [])
        if item.get("LastModified") is not None and item["LastModified"].astimezone(UTC) < cutoff
    ]
    if keys:
        store.delete_objects(Bucket=config.bucket, Delete={"Objects": keys, "Quiet": True})
    return len(keys)


def backup_once(
    config: BackupConfig,
    *,
    now: datetime | None = None,
    store: BackupStore | None = None,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    selected_store = store or _store(config)
    database_size_mb = _database_size_mb(run)
    if database_size_mb >= config.disk_warning_mb:
        logger.warning("prefect_backup_disk_warning database_size_mb=%s", database_size_mb)
    key = f"{BACKUP_PREFIX}{current.strftime('%Y%m%dT%H%M%SZ')}.dump"
    with tempfile.TemporaryDirectory(prefix="prefect-backup-") as directory:
        dump_path = Path(directory) / "prefect.dump"
        run(
            ["pg_dump", "--format=custom", "--file", str(dump_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        selected_store.upload_file(str(dump_path), config.bucket, key)
    deleted = _prune_old_backups(selected_store, config, now=current)
    logger.info("prefect_backup_complete retained_days=%s pruned=%s", config.retention_days, deleted)
    return key


def run_worker(*, stop: Event, interval_seconds: float = BACKUP_INTERVAL_SECONDS) -> None:
    logger.info("prefect_backup_worker_started")
    while not stop.is_set():
        try:
            config = BackupConfig.from_environment()
            if config is None:
                logger.info("prefect_backups_disabled")
            else:
                backup_once(config)
        except Exception as exc:
            logger.error("prefect_backup_failed error_type=%s", type(exc).__name__)
        stop.wait(interval_seconds)
    logger.info("prefect_backup_worker_stopped")


def _stop(stop: Event) -> Callable[[int, FrameType | None], None]:
    def handler(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    return handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    stop = Event()
    signal.signal(signal.SIGTERM, _stop(stop))
    signal.signal(signal.SIGINT, _stop(stop))
    run_worker(stop=stop)


if __name__ == "__main__":
    main()
