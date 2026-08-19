"""Agent service: the single boundary between HTTP and the LangGraph runtime + trace store.

The router owns no agent logic. ``answer`` runs the graph and schedules trace persistence off the
request path; the read methods serve the Agent OS dashboard from the trace store. Pipeline/graph
failures become a typed ``AgentError`` the app boundary renders as HTTP — never a raw stack trace.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import BackgroundTasks
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.config import Settings
from ..chat.repository import ChatRepository
from .config import build_agent_config, is_agents_configured
from .graph import run_agent
from .memory_service import AgentMemoryError, AgentMemoryService
from .recorder import persist_run
from .repository import AgentRepository
from .schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    GuardrailSummary,
    NodeStepRead,
    RunDetail,
    RunSummary,
    ToolCallRead,
)

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
        payload: AgentQueryRequest,
        background_tasks: BackgroundTasks,
        source_access_token: str,
        principal: AuthenticatedPrincipal,
    ) -> AgentQueryResponse:
        """Run the graph, persist the trace off-path, and return the answer + trace id."""
        if not is_agents_configured(self.settings):
            raise AgentError(503, "The agent is not available right now.")

        memory = AgentMemoryService(self._require_session())
        chat_repository = ChatRepository(self._require_session())
        chat_session = (
            chat_repository.get_session_for_user(str(payload.conversation_id), principal.user_id)
            if payload.conversation_id
            else None
        )
        try:
            conversation = memory.conversation(
                conversation_id=str(payload.conversation_id) if payload.conversation_id else None,
                owner_user_uuid=principal.user_id,
                jurisdiction=principal.jurisdiction,
            )
            if payload.memory_decision is None:
                memory.discard_pending(conversation.id)
            evidence = memory.evidence(payload.question, conversation.jurisdiction)
        except AgentMemoryError as exc:
            raise AgentError(exc.status_code, exc.detail) from exc

        if chat_session is not None:
            chat_repository.append_message_for_user(
                session_id=chat_session.session_id,
                user_id=principal.user_id,
                role="user",
                content=payload.question,
            )
            self._require_session().commit()

        config = build_agent_config(self.settings, source_access_token)
        if payload.route == "auto":
            result = run_agent(payload.question, config, principal.jurisdiction, evidence)
        else:
            result = run_agent(
                payload.question,
                config,
                principal.jurisdiction,
                evidence,
                route_preference=payload.route,
            )
        try:
            if payload.memory_decision is not None:
                memory.decide(
                    conversation=conversation,
                    decision=payload.memory_decision,
                    actor_user_uuid=principal.user_id,
                    trace_id=result.trace_id,
                )
            if result.status == "ok":
                _proposal, rejection_reason = memory.create_proposal(
                    conversation=conversation,
                    raw_candidate=result.memory_candidate,
                    trace_id=result.trace_id,
                    question=payload.question,
                )
                if rejection_reason:
                    result.guardrail_events.append(
                        {
                            "layer": "memory",
                            "rule_id": rejection_reason,
                            "category": "content",
                            "outcome": "blocked",
                            "duration_ms": 0,
                        }
                    )
            pending = memory.pending_response(conversation.id)
        except AgentMemoryError as exc:
            raise AgentError(exc.status_code, exc.detail) from exc
        # Guardrail-blocked content is never stored (telemetry standard §8). Chat-session content is
        # NOT suppressed here: Engagement 10 already persists full chat messages under the approved
        # telemetry exception, so a truncated preview of the same content adds no new category of
        # stored data — it just makes chat-routed runs legible in the Agent OS dashboard.
        input_summary, output_summary = (
            (None, None)
            if result.guardrail_events
            else self._summaries(payload.question, result.answer)
        )

        if result.answer and result.status in {"ok", "rejected"}:
            if chat_session is not None:
                chat_repository.append_message_for_user(
                    session_id=chat_session.session_id,
                    user_id=principal.user_id,
                    role="assistant",
                    content=result.answer,
                )
                self._require_session().commit()
            # Success: persist after the response is sent (off the request path).
            background_tasks.add_task(
                persist_run,
                result,
                env=self.settings.app_env,
                input_summary=input_summary,
                output_summary=output_summary,
            )
            return AgentQueryResponse(
                answer=result.answer,
                trace_id=result.trace_id,
                conversation_id=UUID(conversation.id),
                route_taken=result.route_taken,
                memory_proposal=pending,
            )

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
