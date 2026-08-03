"""Transactional persistence queries for confirmed structured agent memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, text
from sqlmodel import Session, col, select

from ..suppliers.models import Supplier
from .memory_validation import ACTIVE_CARRIER_NAMES
from .models import (
    AgentConversation,
    AgentMemoryDecision,
    AgentMemoryFact,
    AgentMemoryProposal,
    AgentMemoryVersion,
)


class AgentMemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_conversation(self, conversation_id: str) -> AgentConversation | None:
        return self.session.get(AgentConversation, conversation_id)

    def add_conversation(self, conversation: AgentConversation) -> None:
        self.session.add(conversation)

    def pending_proposal(self, conversation_id: str) -> AgentMemoryProposal | None:
        return self.session.exec(
            select(AgentMemoryProposal).where(
                AgentMemoryProposal.conversation_id == conversation_id,
                AgentMemoryProposal.status == "pending",
            )
        ).one_or_none()

    def locked_proposal(self, proposal_id: str) -> AgentMemoryProposal | None:
        return self.session.exec(
            select(AgentMemoryProposal).where(AgentMemoryProposal.id == proposal_id).with_for_update()
        ).one_or_none()

    def get_proposal(self, proposal_id: str) -> AgentMemoryProposal | None:
        return self.session.get(AgentMemoryProposal, proposal_id)

    def add_proposal(self, proposal: AgentMemoryProposal) -> None:
        self.session.add(proposal)

    def decision(self, decision_id: str) -> AgentMemoryDecision | None:
        return self.session.exec(
            select(AgentMemoryDecision).where(AgentMemoryDecision.decision_id == decision_id)
        ).one_or_none()

    def add_decision(self, decision: AgentMemoryDecision) -> None:
        self.session.add(decision)

    def supplier(self, carrier_id: str) -> Supplier | None:
        return self.session.get(Supplier, carrier_id)

    def recognized_carrier(self, text_value: str, jurisdiction: str) -> Supplier | None:
        country = "USA" if jurisdiction == "US" else "Spain"
        suppliers = self.session.exec(
            select(Supplier).where(Supplier.country == country, Supplier.status == "active")
        ).all()
        normalized = text_value.casefold()
        matches = [
            supplier
            for supplier in suppliers
            if supplier.name in ACTIVE_CARRIER_NAMES
            and supplier.name.casefold() in normalized
            and any(category.startswith("carrier_") for category in supplier.categories)
        ]
        return matches[0] if len(matches) == 1 else None

    def active_facts(self, carrier_id: str, jurisdiction: str) -> list[AgentMemoryFact]:
        return list(
            self.session.exec(
                select(AgentMemoryFact).where(
                    AgentMemoryFact.carrier_id == carrier_id,
                    AgentMemoryFact.jurisdiction == jurisdiction,
                    col(AgentMemoryFact.active).is_(True),
                )
            ).all()
        )

    def lock_consolidation_key(self, key: str) -> None:
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:memory_key, 0))"),
            {"memory_key": key},
        )

    def consolidated_fact(
        self,
        *,
        carrier_id: str,
        jurisdiction: str,
        kind: str,
        subject_key: str,
    ) -> AgentMemoryFact | None:
        return self.session.exec(
            select(AgentMemoryFact)
            .where(
                AgentMemoryFact.carrier_id == carrier_id,
                AgentMemoryFact.jurisdiction == jurisdiction,
                AgentMemoryFact.kind == kind,
                AgentMemoryFact.subject_key == subject_key,
            )
            .with_for_update()
        ).one_or_none()

    def add_fact(self, fact: AgentMemoryFact) -> None:
        self.session.add(fact)

    def add_version(self, version: AgentMemoryVersion) -> None:
        self.session.add(version)

    def delete_expired_pending(self, cutoff: datetime, *, limit: int) -> int:
        ids = list(
            self.session.exec(
                select(AgentMemoryProposal.id)
                .where(
                    AgentMemoryProposal.status == "pending",
                    AgentMemoryProposal.updated_at < cutoff,
                )
                .order_by(AgentMemoryProposal.updated_at)  # type: ignore[arg-type]
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        if not ids:
            return 0
        result = self.session.execute(delete(AgentMemoryProposal).where(col(AgentMemoryProposal.id).in_(ids)))
        return int(cast(Any, result).rowcount or 0)
