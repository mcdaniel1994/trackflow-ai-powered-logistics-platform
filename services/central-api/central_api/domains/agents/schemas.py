"""Request/response contracts for the LangGraph agent and its trace store.

The query response carries only the model-generated answer plus the ``trace_id`` that links it to
the stored run — never raw retrieval output. The trace read models expose safe metadata only
(node names, timings, statuses, token/cost counts, redacted summaries); raw prompts, completions,
retrieved text, tool arguments, and secrets are never persisted or returned (telemetry standard §8).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AgentQueryRequest(APIModel):
    """A single natural-language question routed through the agent graph."""

    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class AgentQueryResponse(APIModel):
    """The agent's answer plus the id of the persisted run trace."""

    answer: str
    trace_id: str


class ToolCallRead(APIModel):
    """One tool invocation within a run (populated from Part 2 onward)."""

    tool_name: str
    status: str
    duration_ms: int | None = None
    error_type: str | None = None
    output_summary: str | None = None


class NodeStepRead(APIModel):
    """One graph node execution: safe timing/status metadata only."""

    node_name: str
    sequence: int
    status: str
    duration_ms: int | None = None
    tokens: int | None = None
    cost_usd: float | None = None
    notes: str | None = None


class RunSummary(APIModel):
    """List-view row for the Agent OS dashboard."""

    trace_id: str
    agent_name: str
    status: str
    route_taken: str | None = None
    duration_ms: int | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    guardrail_trigger_count: int = 0
    started_at: datetime
    created_at: datetime


class RunDetail(RunSummary):
    """Full run: summary plus the ordered node steps and tool calls."""

    input_summary: str | None = None
    output_summary: str | None = None
    node_steps: list[NodeStepRead] = Field(default_factory=list)
    tool_calls: list[ToolCallRead] = Field(default_factory=list)


class GuardrailSummary(APIModel):
    category: str
    rule_id: str
    outcome: str
    count: int
