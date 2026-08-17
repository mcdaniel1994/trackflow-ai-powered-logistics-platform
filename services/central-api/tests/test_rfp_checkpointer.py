"""Unit proofs for the RFP approval checkpointer's provisioning branch (Engagement 9, Phase 3).

The runtime role has no CREATE privilege, so ``approval_checkpointer`` must run ``setup()`` only when the
tables are absent. These mock the LangGraph saver to prove the branch without a database; the real
CRUD-vs-DDL behaviour is proven against Postgres in ``test_production_migrate`` and ``test_rfp_approval``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from central_api.core.config import Settings
from central_api.domains.rfp import checkpointer as cp

_DB_URL = "postgresql+psycopg2://user:secret@localhost/database"


class _FakeCursor:
    def __init__(self, exists: bool) -> None:
        self._exists = exists

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, _sql: str) -> None:
        return None

    def fetchone(self) -> bool:
        return self._exists


class _FakeConn:
    def __init__(self, exists: bool) -> None:
        self._exists = exists

    def cursor(self, **_kwargs: object) -> _FakeCursor:
        return _FakeCursor(self._exists)


class _FakeSaver:
    def __init__(self, *, tables_present: bool) -> None:
        self.conn = _FakeConn(tables_present)
        self.setup = MagicMock()


def _install(monkeypatch: pytest.MonkeyPatch, saver: _FakeSaver) -> None:
    class _FakePostgresSaver:
        @staticmethod
        @contextmanager
        def from_conn_string(_conn: str) -> Iterator[Any]:
            yield saver

    monkeypatch.setattr(cp, "PostgresSaver", _FakePostgresSaver)


@pytest.fixture(autouse=True)
def _reset_setup_flag() -> Iterator[None]:
    cp._setup_done = False
    yield
    cp._setup_done = False


def test_runtime_skips_setup_when_tables_present(monkeypatch: pytest.MonkeyPatch) -> None:
    saver = _FakeSaver(tables_present=True)
    _install(monkeypatch, saver)
    with cp.approval_checkpointer(Settings(database_url=_DB_URL)):
        pass
    saver.setup.assert_not_called()
    assert cp._setup_done is True


def test_runtime_runs_setup_when_tables_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    saver = _FakeSaver(tables_present=False)
    _install(monkeypatch, saver)
    with cp.approval_checkpointer(Settings(database_url=_DB_URL)):
        pass
    saver.setup.assert_called_once()


def test_setup_runs_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    saver = _FakeSaver(tables_present=False)
    _install(monkeypatch, saver)
    with cp.approval_checkpointer(Settings(database_url=_DB_URL)):
        pass
    with cp.approval_checkpointer(Settings(database_url=_DB_URL)):
        pass
    saver.setup.assert_called_once()


def test_provision_checkpointer_tables_runs_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    saver = _FakeSaver(tables_present=False)
    _install(monkeypatch, saver)
    cp.provision_checkpointer_tables(_DB_URL)
    saver.setup.assert_called_once()
