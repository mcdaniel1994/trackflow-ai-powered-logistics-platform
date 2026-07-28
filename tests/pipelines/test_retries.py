"""Explicit transient-only retry proofs for reporting computation."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from pipelines.business_performance.retries import (
    is_transient_connectivity_failure,
    run_with_transient_retries,
)


class DatabaseFailure(Exception):
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate
        super().__init__("database operation failed")


def test_retries_allowlisted_connectivity_failure_then_succeeds() -> None:
    calls = 0
    sleeps: list[float] = []

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OperationalError("connect", {}, DatabaseFailure("08006"))
        return "ok"

    assert run_with_transient_retries(operation, sleeper=sleeps.append) == "ok"
    assert calls == 3
    assert sleeps == [0.25, 0.5]


def test_nontransient_database_failure_is_not_retried() -> None:
    failure = OperationalError("select", {}, DatabaseFailure("23505"))
    assert is_transient_connectivity_failure(failure) is False
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise failure

    try:
        run_with_transient_retries(operation, sleeper=lambda _delay: None)
    except OperationalError as raised:
        assert raised is failure
    else:
        raise AssertionError("nontransient failure was swallowed")
    assert calls == 1


def test_explicit_socket_and_text_allowlist_paths_and_exhaustion() -> None:
    assert is_transient_connectivity_failure(ConnectionRefusedError()) is True
    assert (
        is_transient_connectivity_failure(
            OSError("server closed the connection unexpectedly")
        )
        is True
    )
    calls = 0

    def timeout() -> None:
        nonlocal calls
        calls += 1
        raise TimeoutError

    with pytest.raises(TimeoutError):
        run_with_transient_retries(timeout, delays=(), sleeper=lambda _delay: None)
    assert calls == 1
