"""Best-effort, off-request-path persistence of a completed agent run trace.

Mirrors the telemetry recorder: writes in a short-lived session and swallows every failure, so a
trace-store outage never breaks or slows the agent response. On the success path the service
schedules this via ``BackgroundTasks`` (runs after the HTTP response); on the error path it is
called synchronously (still swallowing) so failed runs are not lost.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlmodel import Session

from ...db.session import get_engine
from .graph import AgentRunResult
from .models import AgentNodeStep, AgentRun

logger = logging.getLogger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def persist_run(
    result: AgentRunResult,
    *,
    env: str,
    input_summary: str | None,
    output_summary: str | None,
) -> None:
    """Insert one run and its node steps; never raise."""
    try:
        run = AgentRun(
            trace_id=result.trace_id,
            agent_name=result.agent_name,
            env=env,
            status=result.status,
            route_taken=result.route_taken,
            started_at=result.started_at,
            ended_at=result.ended_at,
            duration_ms=result.duration_ms,
            total_tokens=None,
            total_cost_usd=None,
            guardrail_trigger_count=0,
            input_summary=input_summary,
            output_summary=output_summary,
        )
        with Session(get_engine()) as session:
            session.add(run)
            session.flush()  # assign run.id for the child rows
            for step in result.steps:
                session.add(
                    AgentNodeStep(
                        run_id=run.id,  # type: ignore[arg-type]
                        node_name=step["node_name"],
                        sequence=step["sequence"],
                        status=step["status"],
                        started_at=_parse_iso(step.get("started_at")) or result.started_at,
                        ended_at=_parse_iso(step.get("ended_at")),
                        duration_ms=step.get("duration_ms"),
                        tokens=step.get("tokens"),
                        cost_usd=step.get("cost_usd"),
                        notes=step.get("notes"),
                    )
                )
            session.commit()
    except Exception as exc:
        # The trace sink must never break the caller: log the type and swallow.
        logger.warning("agent_trace_persist_failed trace_id=%s error_type=%s", result.trace_id, type(exc).__name__)
