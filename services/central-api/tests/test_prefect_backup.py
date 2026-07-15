"""Isolated Prefect database backup behavior and safe degradation."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from scripts import prefect_db_backup

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


class Store:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str]] = []
        self.deleted: list[str] = []

    def upload_file(self, Filename: str, Bucket: str, Key: str) -> object:
        assert Path(Filename).exists()
        self.uploaded.append((Bucket, Key))
        return {}

    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict[str, Any]:
        assert Bucket == "private-backups"
        assert Prefix == "prefect-backups/"
        return {
            "Contents": [
                {"Key": "prefect-backups/old.dump", "LastModified": NOW - timedelta(days=8)},
                {"Key": "prefect-backups/new.dump", "LastModified": NOW - timedelta(days=1)},
            ]
        }

    def delete_objects(self, *, Bucket: str, Delete: dict[str, Any]) -> object:
        assert Bucket == "private-backups"
        self.deleted.extend(item["Key"] for item in Delete["Objects"])
        return {}


def _config() -> prefect_db_backup.BackupConfig:
    return prefect_db_backup.BackupConfig(
        "private-backups",
        "https://example.invalid",
        "scoped-id",
        "scoped-secret",
        disk_warning_mb=10,
    )


def test_backup_dumps_uploads_samples_and_prunes(monkeypatch: pytest.MonkeyPatch) -> None:
    store = Store()
    commands: list[list[str]] = []
    warnings: list[tuple[str, int]] = []
    monkeypatch.setattr(
        prefect_db_backup.logger,
        "warning",
        lambda message, value: warnings.append((message, value)),
    )

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "psql":
            return subprocess.CompletedProcess(command, 0, stdout=str(20 * 1024 * 1024), stderr="")
        Path(command[command.index("--file") + 1]).write_bytes(b"safe custom dump")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    key = prefect_db_backup.backup_once(_config(), now=NOW, store=store, run=run)
    assert key == "prefect-backups/20260715T120000Z.dump"
    assert [command[0] for command in commands] == ["psql", "pg_dump"]
    assert store.uploaded == [("private-backups", key)]
    assert store.deleted == ["prefect-backups/old.dump"]
    assert warnings == [("prefect_backup_disk_warning database_size_mb=%s", 20)]


def test_absent_backup_configuration_is_a_fixed_nonblocking_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "PREFECT_BACKUP_R2_BUCKET",
        "PREFECT_BACKUP_R2_ENDPOINT",
        "PREFECT_BACKUP_R2_ACCESS_KEY_ID",
        "PREFECT_BACKUP_R2_SECRET_ACCESS_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    stop = Event()
    notices: list[str] = []
    monkeypatch.setattr(stop, "wait", lambda _seconds: stop.set() or True)
    monkeypatch.setattr(
        prefect_db_backup.logger,
        "info",
        lambda message, *_args: notices.append(message),
    )
    prefect_db_backup.run_worker(stop=stop, interval_seconds=0.001)
    assert "prefect_backups_disabled" in notices
