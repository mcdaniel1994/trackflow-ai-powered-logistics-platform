"""Request/response contracts for the LangGraph agent and its trace store.

The query response carries only the model-generated answer plus the ``trace_id`` that links it to
the stored run — never raw retrieval output. The trace read models expose safe metadata only
(node names, timings, statuses, token/cost counts, redacted summaries); raw prompts, completions,
retrieved text, tool arguments, and secrets are never persisted or returned (telemetry standard §8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


MemoryKind = Literal[
    "carrier_coverage_correction",
    "carrier_assignment_correction",
    "recurring_operational_pattern",
    "carrier_b2b_reporting_preference",
]


class MemoryCandidate(APIModel):
    carrier_id: UUID
    jurisdiction: Literal["US", "ES"]
    kind: MemoryKind
    subject_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    fact: str = Field(min_length=1, max_length=500)
    recurrence_count: int = Field(ge=2, le=1_000_000)
    effective_at: datetime | None = None


class MemoryDecisionRequest(APIModel):
    decision_id: UUID
    proposal_id: UUID
    action: Literal["approve", "reject", "edit"]
    edited_candidate: MemoryCandidate | None = None

    @model_validator(mode="after")
    def edit_contract(self) -> MemoryDecisionRequest:
        if self.action == "edit" and self.edited_candidate is None:
            raise ValueError("edited_candidate is required for edit")
        if self.action != "edit" and self.edited_candidate is not None:
            raise ValueError("edited_candidate is allowed only for edit")
        return self


class AgentQueryRequest(APIModel):
    """A typed conversation turn; plain text can never imply a memory decision."""

    question: str = Field(min_length=1, max_length=1000)
    conversation_id: UUID | None = None
    memory_decision: MemoryDecisionRequest | None = None

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class MemoryProposalResponse(APIModel):
    proposal_id: UUID
    candidate: MemoryCandidate


class AgentQueryResponse(APIModel):
    """The guarded answer, conversation, trace, and exact pending proposal when one exists."""

    answer: str
    trace_id: str
    conversation_id: UUID
    memory_proposal: MemoryProposalResponse | None = None


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
