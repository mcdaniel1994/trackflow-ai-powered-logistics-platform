"""Allowlisted reporting-executor selection with lazy implementation imports."""

from __future__ import annotations

import os
from typing import Final, Literal

from .runner import RunExecutor

ExecutorName = Literal["prefect", "direct_sql"]

EXECUTOR_ENV: Final = "REPORTING_EXECUTOR"
DEFAULT_EXECUTOR: Final[ExecutorName] = "prefect"
SUPPORTED_EXECUTORS: Final = frozenset({DEFAULT_EXECUTOR, "direct_sql"})


def executor_name_from_environment() -> ExecutorName:
    """Return an allowlisted executor name, preserving Prefect as the code default."""
    value = os.environ.get(EXECUTOR_ENV, DEFAULT_EXECUTOR).strip().lower()
    if value not in SUPPORTED_EXECUTORS:
        raise ValueError("unsupported reporting executor")
    return value


def executor_from_environment() -> tuple[ExecutorName, RunExecutor]:
    """Load only the selected executor implementation."""
    name = executor_name_from_environment()
    if name == "direct_sql":
        from .direct_executor import direct_sql_executor

        return name, direct_sql_executor

    from .flows import prefect_executor

    return name, prefect_executor
