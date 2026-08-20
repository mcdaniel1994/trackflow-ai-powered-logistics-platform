"""Reporting executor selection and lazy import boundaries."""

from __future__ import annotations

import pytest

from pipelines.business_performance import executor_selection
from pipelines.business_performance.direct_executor import direct_sql_executor


def test_executor_defaults_to_direct_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPORTING_EXECUTOR", raising=False)
    assert executor_selection.executor_from_environment() == (
        "direct_sql",
        direct_sql_executor,
    )


def test_executor_selects_direct_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPORTING_EXECUTOR", "direct_sql")
    assert executor_selection.executor_from_environment() == (
        "direct_sql",
        direct_sql_executor,
    )


def test_executor_rejects_retired_prefect_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment left pinned to the retired orchestrator must fail closed, not fall back."""
    monkeypatch.setenv("REPORTING_EXECUTOR", "prefect")
    with pytest.raises(ValueError, match=r"^unsupported reporting executor$"):
        executor_selection.executor_from_environment()


def test_executor_rejects_unknown_value_without_echoing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPORTING_EXECUTOR", "postgresql://user:secret@private")
    with pytest.raises(ValueError, match=r"^unsupported reporting executor$"):
        executor_selection.executor_from_environment()
