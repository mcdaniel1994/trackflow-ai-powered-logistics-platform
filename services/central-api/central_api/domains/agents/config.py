"""Adapt Central API settings into the agent runtime's configuration.

Phase 1's graph reuses the Engagement 7 RAG pipeline (``retrieve`` + ``generate_answer``), so the
agent is "configured" under the same condition RAG is, plus its own enable flag. Later phases add
the OpenAI routing model and tool endpoints here.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipelines.rag import RagConfig  # type: ignore[import-untyped]

from ...core.config import Settings
from ..rag.config import build_rag_config, is_rag_configured


@dataclass(frozen=True)
class AgentConfig:
    """Everything the agent graph needs for one run."""

    agent_name: str
    rag: RagConfig
    min_score: float
    agent_model: str
    route_timeout_seconds: float
    ticket_timeout_seconds: float


def is_agents_configured(settings: Settings) -> bool:
    """True only when the agent is enabled and its RAG dependency is fully configured."""
    return bool(settings.agents_enabled and is_rag_configured(settings))


def build_agent_config(settings: Settings) -> AgentConfig:
    """Translate validated settings into an AgentConfig (reusing the RAG mapping)."""
    rag = build_rag_config(settings)
    return AgentConfig(
        agent_name=settings.agent_name,
        rag=rag,
        min_score=rag.min_score,
        agent_model=settings.agent_model,
        route_timeout_seconds=settings.agent_route_timeout_seconds,
        ticket_timeout_seconds=settings.agent_ticket_timeout_seconds,
    )
