"""Allowlisted reporting-executor selection.

Prefect was retired in August 2026 (see
``docs/archive/prefect-orchestration-retirement.md``); direct SQL is the only
executor. ``REPORTING_EXECUTOR`` is still honoured and still fails closed on an
unrecognised value, so a stale deployment environment cannot silently select an
executor that no longer exists.
"""

from __future__ import annotations

import os
from typing import Final, Literal

from .runner import RunExecutor

ExecutorName = Literal["direct_sql"]

EXECUTOR_ENV: Final = "REPORTING_EXECUTOR"
DEFAULT_EXECUTOR: Final[ExecutorName] = "direct_sql"
SUPPORTED_EXECUTORS: Final = frozenset({DEFAULT_EXECUTOR})


def executor_name_from_environment() -> ExecutorName:
    """Return the allowlisted executor name, rejecting anything else."""
    value = os.environ.get(EXECUTOR_ENV, DEFAULT_EXECUTOR).strip().lower()
    if value not in SUPPORTED_EXECUTORS:
        raise ValueError("unsupported reporting executor")
    return DEFAULT_EXECUTOR


def executor_from_environment() -> tuple[ExecutorName, RunExecutor]:
    """Load the direct SQL executor."""
    name = executor_name_from_environment()
    from .direct_executor import direct_sql_executor

    return name, direct_sql_executor
