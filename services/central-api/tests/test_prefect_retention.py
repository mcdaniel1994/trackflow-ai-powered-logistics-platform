"""Prefect history retention uses only the orchestration API."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from scripts import prune_prefect_runs


def test_prune_deletes_only_old_terminal_flow_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal_id = uuid4()
    running_id = uuid4()
    deleted: list[UUID] = []

    class Client:
        async def read_flow_runs(self, **_kwargs: object) -> list[object]:
            return [
                SimpleNamespace(id=terminal_id, state=SimpleNamespace(is_final=lambda: True)),
                SimpleNamespace(id=running_id, state=SimpleNamespace(is_final=lambda: False)),
            ]

        async def delete_flow_run(self, run_id: UUID) -> None:
            deleted.append(run_id)

    class Context:
        async def __aenter__(self) -> Client:
            return Client()

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(prune_prefect_runs, "get_client", Context)
    count = asyncio.run(prune_prefect_runs._prune_before(datetime(2026, 6, 15, tzinfo=UTC)))
    assert count == 1
    assert deleted == [terminal_id]


def test_retention_days_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREFECT_RUN_RETENTION_DAYS", "0")
    with pytest.raises(ValueError, match="positive"):
        prune_prefect_runs.prune_once()
