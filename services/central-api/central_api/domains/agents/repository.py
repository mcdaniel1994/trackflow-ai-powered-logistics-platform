"""Read + retention access for the agent trace store.

All SQL lives here, out of the service and router. Reads power the Agent OS dashboard; the bounded
``delete_before`` supports the retention runner (no unbounded deletes on the trace tables).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import func
from sqlmodel import Session, select

from .models import AgentGuardrailEvent, AgentNodeStep, AgentRun, AgentToolCall

_run_table = AgentRun.__table__  # type: ignore[attr-defined]


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_runs(self, *, limit: int = 50, agent_name: str | None = None, status: str | None = None) -> list[AgentRun]:
        statement = select(AgentRun).order_by(AgentRun.created_at.desc())  # type: ignore[attr-defined]
        if agent_name:
            statement = statement.where(AgentRun.agent_name == agent_name)
        if status:
            statement = statement.where(AgentRun.status == status)
        statement = statement.limit(limit)
        return list(self.session.exec(statement).all())

    def get_run(self, trace_id: str) -> AgentRun | None:
        return self.session.exec(select(AgentRun).where(AgentRun.trace_id == trace_id)).first()

    def steps_for(self, run_id: int) -> list[AgentNodeStep]:
        statement = (
            select(AgentNodeStep)
            .where(AgentNodeStep.run_id == run_id)
            .order_by(
                AgentNodeStep.sequence  # type: ignore[arg-type]
            )
        )
        return list(self.session.exec(statement).all())

    def tool_calls_for(self, run_id: int) -> list[AgentToolCall]:
        statement = (
            select(AgentToolCall)
            .where(AgentToolCall.run_id == run_id)
            .order_by(
                AgentToolCall.id  # type: ignore[arg-type]
            )
        )
        return list(self.session.exec(statement).all())

    def guardrail_summary(self) -> list[tuple[str, str, str, int]]:
        statement = (
            select(
                AgentGuardrailEvent.category,
                AgentGuardrailEvent.rule_id,
                AgentGuardrailEvent.outcome,
                func.count(),
            )
            .group_by(AgentGuardrailEvent.category, AgentGuardrailEvent.rule_id, AgentGuardrailEvent.outcome)
            .order_by(AgentGuardrailEvent.category, AgentGuardrailEvent.rule_id)
        )
        return [
            (str(category), str(rule), str(outcome), int(count))
            for category, rule, outcome, count in self.session.exec(statement).all()
        ]

    def delete_before(self, cutoff: datetime) -> int:
        """Prune runs created before ``cutoff``. Child rows cascade via ON DELETE CASCADE."""
        result = self.session.execute(_run_table.delete().where(_run_table.c.created_at < cutoff))
        return int(cast(Any, result).rowcount or 0)
