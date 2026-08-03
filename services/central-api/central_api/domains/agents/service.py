"""Agent service: the single boundary between HTTP and the LangGraph runtime + trace store.

The router owns no agent logic. ``answer`` runs the graph and schedules trace persistence off the
request path; the read methods serve the Agent OS dashboard from the trace store. Pipeline/graph
failures become a typed ``AgentError`` the app boundary renders as HTTP — never a raw stack trace.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import BackgroundTasks
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.config import Settings
from .config import build_agent_config, is_agents_configured
from .graph import run_agent
from .recorder import persist_run
from .repository import AgentRepository
from .schemas import AgentQueryResponse, GuardrailSummary, NodeStepRead, RunDetail, RunSummary, ToolCallRead

logger = logging.getLogger(__name__)

_SUMMARY_MAX_CHARS = 200


@dataclass
class AgentError(Exception):
    """Typed agent failure translated to HTTP only at the application boundary."""

    status_code: int
    detail: str


class AgentService:
    def __init__(self, settings: Settings, session: Session | None = None) -> None:
        self.settings = settings
        self._session = session

    # ------------------------------------------------------------------ query (write path)
    def answer(
        self,
        question: str,
        background_tasks: BackgroundTasks,
        source_access_token: str,
        principal: AuthenticatedPrincipal,
    ) -> AgentQueryResponse:
        """Run the graph, persist the trace off-path, and return the answer + trace id."""
        if not is_agents_configured(self.settings):
            raise AgentError(503, "The agent is not available right now.")

        config = build_agent_config(self.settings, source_access_token)
        result = run_agent(question, config, principal.jurisdiction)
        input_summary, output_summary = (
            (None, None) if result.guardrail_events else self._summaries(question, result.answer)
        )

        if result.answer and result.status in {"ok", "rejected"}:
            # Success: persist after the response is sent (off the request path).
            background_tasks.add_task(
                persist_run,
                result,
                env=self.settings.app_env,
                input_summary=input_summary,
                output_summary=output_summary,
            )
            return AgentQueryResponse(answer=result.answer, trace_id=result.trace_id)

        # Error/rejected: persist synchronously (still swallowing) so failed runs are not lost.
        persist_run(result, env=self.settings.app_env, input_summary=input_summary, output_summary=output_summary)
        logger.warning("agent_run_failed trace_id=%s", result.trace_id)
        raise AgentError(502, "The agent is temporarily unavailable.")

    # ------------------------------------------------------------------ reads (dashboard)
    def list_runs(
        self, *, limit: int = 50, agent_name: str | None = None, status: str | None = None
    ) -> list[RunSummary]:
        repo = AgentRepository(self._require_session())
        runs = repo.list_runs(limit=limit, agent_name=agent_name, status=status)
        return [RunSummary.model_validate(run) for run in runs]

    def get_run(self, trace_id: str) -> RunDetail:
        repo = AgentRepository(self._require_session())
        run = repo.get_run(trace_id)
        if run is None or run.id is None:
            raise AgentError(404, "Run not found.")
        detail = RunDetail.model_validate(run)
        detail.node_steps = [NodeStepRead.model_validate(step) for step in repo.steps_for(run.id)]
        detail.tool_calls = [ToolCallRead.model_validate(call) for call in repo.tool_calls_for(run.id)]
        return detail

    def guardrail_summary(self) -> list[GuardrailSummary]:
        return [
            GuardrailSummary(category=category, rule_id=rule_id, outcome=outcome, count=count)
            for category, rule_id, outcome, count in AgentRepository(self._require_session()).guardrail_summary()
        ]

    # ------------------------------------------------------------------ helpers
    def _require_session(self) -> Session:
        if self._session is None:
            raise AgentError(500, "Trace store session is not available.")
        return self._session

    def _summaries(self, question: str, answer: str | None) -> tuple[str | None, str | None]:
        """Redacted previews for the dashboard — only when content capture is explicitly enabled.

        By default (``agents_store_content=False``) no raw prompt/answer content is persisted
        (telemetry standard §8); capturing content is an explicit, truncated, opt-in decision.
        """
        if not self.settings.agents_store_content:
            return None, None
        return (
            question[:_SUMMARY_MAX_CHARS],
            answer[:_SUMMARY_MAX_CHARS] if answer else None,
        )
