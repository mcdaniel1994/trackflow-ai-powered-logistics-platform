"""Adapt Central API settings into the agent runtime's configuration.

The graph reuses the Engagement 7 RAG pipeline (``retrieve`` + ``generate_answer``), so the agent
is "configured" under the same condition RAG is, plus its own enable flag. Phase 3 binds the
internal MCP transport, public OAuth resource identifier, confidential client, and ephemeral
request token here without placing credentials in graph state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    mcp_url: str
    mcp_resource_url: str
    oauth_token_url: str
    mcp_oauth_client_id: str
    mcp_oauth_client_secret: str = field(repr=False)
    source_access_token: str = field(repr=False)


def is_agents_configured(settings: Settings) -> bool:
    """True only when the agent is enabled and its RAG dependency is fully configured."""
    return bool(
        settings.agents_enabled
        and is_rag_configured(settings)
        and settings.agent_mcp_url.strip()
        and settings.agent_mcp_resource_url.strip()
        and settings.agent_mcp_oauth_client_id.strip()
        and settings.agent_mcp_oauth_client_secret.get_secret_value().strip()
    )


def build_agent_config(settings: Settings, source_access_token: str) -> AgentConfig:
    """Translate validated settings into an AgentConfig (reusing the RAG mapping)."""
    rag = build_rag_config(settings)
    return AgentConfig(
        agent_name=settings.agent_name,
        rag=rag,
        min_score=rag.min_score,
        agent_model=settings.agent_model,
        route_timeout_seconds=settings.agent_route_timeout_seconds,
        ticket_timeout_seconds=settings.agent_ticket_timeout_seconds,
        mcp_url=settings.agent_mcp_url,
        mcp_resource_url=settings.agent_mcp_resource_url,
        oauth_token_url=f"{settings.identity_oauth_internal_url.rstrip('/')}/oauth/token",
        mcp_oauth_client_id=settings.agent_mcp_oauth_client_id,
        mcp_oauth_client_secret=settings.agent_mcp_oauth_client_secret.get_secret_value(),
        source_access_token=source_access_token,
    )
