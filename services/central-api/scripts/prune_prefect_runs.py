"""Delete old terminal Prefect flow runs through the orchestration API only."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterExpectedStartTime
from prefect.client.schemas.objects import FlowRun
from prefect.types._datetime import DateTime


def _retention_days() -> int:
    value = int(os.environ.get("PREFECT_RUN_RETENTION_DAYS", "30"))
    if value < 1:
        raise ValueError("PREFECT_RUN_RETENTION_DAYS must be positive")
    return value


async def _prune_before(cutoff: datetime) -> int:
    async with get_client() as client:
        old_runs: list[FlowRun] = []
        offset = 0
        while True:
            page = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    expected_start_time=FlowRunFilterExpectedStartTime(before_=DateTime.instance(cutoff))
                ),
                limit=200,
                offset=offset,
            )
            old_runs.extend(run for run in page if run.state is not None and run.state.is_final())
            if len(page) < 200:
                break
            offset += len(page)
        for run in old_runs:
            await client.delete_flow_run(run.id)
        return len(old_runs)


def prune_once(*, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=_retention_days())
    return asyncio.run(_prune_before(cutoff))
