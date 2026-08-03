"""Trace retention is bounded, cascading, idempotent, and isolated from memory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.domains.agents.models import (
    AgentConversation,
    AgentGuardrailEvent,
    AgentMemoryDecision,
    AgentMemoryFact,
    AgentMemoryProposal,
    AgentMemoryVersion,
    AgentNodeStep,
    AgentRun,
    AgentToolCall,
)
from central_api.domains.agents.repository import AgentRepository
from central_api.domains.suppliers.models import Supplier


def _trace(session: Session, trace_id: str, created_at: datetime) -> None:
    run = AgentRun(
        trace_id=trace_id,
        agent_name="trackflow-cx-agent",
        env="test",
        status="ok",
        started_at=created_at,
        created_at=created_at,
    )
    session.add(run)
    session.flush()
    assert run.id is not None
    step = AgentNodeStep(
        run_id=run.id,
        node_name="route",
        sequence=1,
        status="ok",
        started_at=created_at,
    )
    session.add(step)
    session.flush()
    session.add(AgentToolCall(run_id=run.id, step_id=step.id, tool_name="ticket_status", status="ok"))
    session.add(
        AgentGuardrailEvent(
            run_id=run.id,
            layer="input",
            rule_id="scope",
            category="content",
            outcome="redirected",
        )
    )


def test_delete_before_is_bounded_cascading_and_idempotent(engine: Engine) -> None:
    now = datetime.now(UTC)
    with Session(engine) as session:
        _trace(session, "expired-a", now - timedelta(days=9))
        _trace(session, "expired-b", now - timedelta(days=8))
        _trace(session, "recent", now - timedelta(days=1))
        session.commit()

        repo = AgentRepository(session)
        assert repo.delete_before(now - timedelta(days=7), limit=1) == 1
        session.commit()
        assert repo.delete_before(now - timedelta(days=7), limit=1) == 1
        session.commit()
        assert repo.delete_before(now - timedelta(days=7), limit=1) == 0
        session.commit()

        assert repo.get_run("recent") is not None
        assert session.exec(select(func.count()).select_from(AgentNodeStep)).one() == 1
        assert session.exec(select(func.count()).select_from(AgentToolCall)).one() == 1
        assert session.exec(select(func.count()).select_from(AgentGuardrailEvent)).one() == 1


def test_trace_pruning_preserves_all_memory_records(engine: Engine) -> None:
    now = datetime.now(UTC)
    with Session(engine) as session:
        carrier = Supplier(
            name="Retention Test Carrier",
            country="USA",
            categories=["carrier_last_mile"],
            rate_per_shipment=5.0,
            currency="USD",
            status="active",
        )
        session.add(carrier)
        session.flush()
        conversation = AgentConversation(owner_user_uuid="11111111-1111-4111-8111-111111111111", jurisdiction="US")
        session.add(conversation)
        session.flush()
        candidate = {
            "carrier_id": carrier.id,
            "jurisdiction": "US",
            "kind": "recurring_operational_pattern",
            "subject_key": "retention_pattern",
            "fact": "A confirmed recurring pattern.",
            "recurrence_count": 2,
        }
        proposal = AgentMemoryProposal(conversation_id=conversation.id, trace_id="expired-trace", **candidate)
        fact = AgentMemoryFact(**candidate)
        session.add(proposal)
        session.add(fact)
        session.flush()
        session.add(
            AgentMemoryDecision(
                decision_id="22222222-2222-4222-8222-222222222222",
                proposal_id=proposal.id,
                conversation_id=conversation.id,
                actor_user_uuid=conversation.owner_user_uuid,
                trace_id="expired-trace",
                action="approve",
                outcome="approved",
                reason_code="explicit_approval",
                fact_id=fact.id,
            )
        )
        session.add(
            AgentMemoryVersion(
                fact_id=fact.id,
                version=1,
                actor_user_uuid=conversation.owner_user_uuid,
                proposal_id=proposal.id,
                decision_id="22222222-2222-4222-8222-222222222222",
                trace_id="expired-trace",
                **candidate,
            )
        )
        _trace(session, "expired-trace", now - timedelta(days=9))
        session.commit()

        assert AgentRepository(session).delete_before(now - timedelta(days=7)) == 1
        session.commit()

        for model in (AgentConversation, AgentMemoryProposal, AgentMemoryFact, AgentMemoryDecision, AgentMemoryVersion):
            assert session.exec(select(func.count()).select_from(model)).one() == 1


def test_invalid_retention_batch_is_rejected(engine: Engine) -> None:
    with Session(engine) as session, pytest.raises(ValueError, match="between 1 and 5000"):
        AgentRepository(session).delete_before(datetime.now(UTC), limit=0)
