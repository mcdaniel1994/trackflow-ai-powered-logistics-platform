"""Human-confirmed structured memory orchestration and ownership rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from .memory_repository import AgentMemoryRepository
from .memory_validation import MemoryValidationError, validate_memory_candidate
from .models import (
    AgentConversation,
    AgentMemoryDecision,
    AgentMemoryFact,
    AgentMemoryProposal,
    AgentMemoryVersion,
)
from .schemas import MemoryCandidate, MemoryDecisionRequest, MemoryProposalResponse


@dataclass(frozen=True)
class AgentMemoryError(ValueError):
    status_code: int
    detail: str


class _CandidateValues(TypedDict):
    carrier_id: str
    jurisdiction: str
    kind: str
    subject_key: str
    fact: str
    recurrence_count: int
    effective_at: datetime | None


class AgentMemoryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AgentMemoryRepository(session)

    def conversation(
        self,
        *,
        conversation_id: str | None,
        owner_user_uuid: str,
        jurisdiction: str | None,
    ) -> AgentConversation:
        if jurisdiction not in {"US", "ES"}:
            raise AgentMemoryError(403, "An administrator must assign your policy jurisdiction first.")
        row = self.repository.get_conversation(conversation_id) if conversation_id else None
        if conversation_id and row is None:
            raise AgentMemoryError(404, "Conversation not found.")
        if row is not None:
            if row.owner_user_uuid != owner_user_uuid:
                raise AgentMemoryError(403, "Conversation access is not authorized.")
            if row.jurisdiction != jurisdiction:
                raise AgentMemoryError(403, "Conversation jurisdiction no longer matches your account.")
            row.updated_at = datetime.now(UTC)
            self.session.add(row)
            self.session.commit()
            return row

        row = AgentConversation(owner_user_uuid=owner_user_uuid, jurisdiction=jurisdiction)
        self.repository.add_conversation(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def discard_pending(self, conversation_id: str) -> None:
        pending = self.repository.pending_proposal(conversation_id)
        if pending is None:
            return
        now = datetime.now(UTC)
        pending.status = "discarded"
        pending.decided_at = now
        pending.updated_at = now
        self.session.add(pending)
        self.session.commit()

    def evidence(self, question: str, jurisdiction: str) -> list[dict[str, object]]:
        carrier = self.repository.recognized_carrier(question, jurisdiction)
        if carrier is None:
            return []
        return [
            {
                "source_document": f"memory-{fact.id}",
                "section": "confirmed carrier memory",
                "text": fact.fact,
                "subject_key": fact.subject_key,
                "carrier_name": carrier.name,
                "jurisdiction": fact.jurisdiction,
            }
            for fact in self.repository.active_facts(carrier.id, jurisdiction)
        ]

    def create_proposal(
        self,
        *,
        conversation: AgentConversation,
        raw_candidate: dict[str, object] | None,
        trace_id: str,
        question: str,
    ) -> tuple[AgentMemoryProposal | None, str | None]:
        if raw_candidate is None or self.repository.pending_proposal(conversation.id) is not None:
            return self.repository.pending_proposal(conversation.id), None
        try:
            candidate = MemoryCandidate.model_validate(raw_candidate)
            supplier = self.repository.supplier(str(candidate.carrier_id))
            validate_memory_candidate(
                candidate,
                supplier=supplier,
                authenticated_jurisdiction=conversation.jurisdiction,
            )
            recognized = self.repository.recognized_carrier(question, conversation.jurisdiction)
            if recognized is None:
                raise MemoryValidationError("carrier_not_recognized")
            if recognized.id != str(candidate.carrier_id):
                raise MemoryValidationError("carrier_mismatch")
        except (ValidationError, MemoryValidationError) as exc:
            reason = exc.reason_code if isinstance(exc, MemoryValidationError) else "candidate_schema"
            return None, reason

        proposal = AgentMemoryProposal(
            conversation_id=conversation.id,
            trace_id=trace_id,
            **self._candidate_values(candidate),
        )
        self.repository.add_proposal(proposal)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return self.repository.pending_proposal(conversation.id), None
        self.session.refresh(proposal)
        return proposal, None

    def decide(
        self,
        *,
        conversation: AgentConversation,
        decision: MemoryDecisionRequest,
        actor_user_uuid: str,
        trace_id: str,
    ) -> AgentMemoryDecision:
        existing = self.repository.decision(str(decision.decision_id))
        if existing is not None:
            self._require_decision_owner(existing, conversation, actor_user_uuid)
            self._require_identical(existing, decision)
            return existing

        proposal = self.repository.locked_proposal(str(decision.proposal_id))
        existing = self.repository.decision(str(decision.decision_id))
        if existing is not None:
            self._require_decision_owner(existing, conversation, actor_user_uuid)
            self._require_identical(existing, decision)
            return existing
        if proposal is None or proposal.conversation_id != conversation.id:
            raise AgentMemoryError(404, "Memory proposal not found.")
        if proposal.status != "pending":
            raise AgentMemoryError(409, "Memory proposal is no longer pending.")

        now = datetime.now(UTC)
        fact_id: str | None = None
        if decision.action == "edit":
            assert decision.edited_candidate is not None
            self._validate(decision.edited_candidate, conversation.jurisdiction)
            for key, value in self._candidate_values(decision.edited_candidate).items():
                setattr(proposal, key, value)
            proposal.trace_id = trace_id
            proposal.updated_at = now
            outcome, reason = "edited", "human_edit"
        elif decision.action == "reject":
            proposal.status = "rejected"
            proposal.decided_at = now
            proposal.updated_at = now
            outcome, reason = "rejected", "human_rejected"
        else:
            candidate = self._proposal_candidate(proposal)
            self._validate(candidate, conversation.jurisdiction)
            fact_id = self._approve(
                proposal=proposal,
                candidate=candidate,
                actor_user_uuid=actor_user_uuid,
                decision_id=str(decision.decision_id),
                trace_id=trace_id,
            )
            proposal.status = "approved"
            proposal.decided_at = now
            proposal.updated_at = now
            outcome, reason = "approved", "human_confirmed"

        audit = AgentMemoryDecision(
            decision_id=str(decision.decision_id),
            proposal_id=proposal.id,
            conversation_id=conversation.id,
            actor_user_uuid=actor_user_uuid,
            trace_id=trace_id,
            action=decision.action,
            outcome=outcome,
            reason_code=reason,
            fact_id=fact_id,
        )
        self.session.add(proposal)
        self.repository.add_decision(audit)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            existing = self.repository.decision(str(decision.decision_id))
            if existing is not None:
                self._require_decision_owner(existing, conversation, actor_user_uuid)
                self._require_identical(existing, decision)
                return existing
            raise AgentMemoryError(409, "Memory decision conflicted with another request.") from exc
        self.session.refresh(audit)
        return audit

    def pending_response(self, conversation_id: str) -> MemoryProposalResponse | None:
        proposal = self.repository.pending_proposal(conversation_id)
        if proposal is None:
            return None
        return MemoryProposalResponse(
            proposal_id=UUID(proposal.id),
            candidate=self._proposal_candidate(proposal),
        )

    def _approve(
        self,
        *,
        proposal: AgentMemoryProposal,
        candidate: MemoryCandidate,
        actor_user_uuid: str,
        decision_id: str,
        trace_id: str,
    ) -> str:
        values = self._candidate_values(candidate)
        key = "|".join((values["carrier_id"], values["jurisdiction"], values["kind"], values["subject_key"]))
        self.repository.lock_consolidation_key(key)
        fact = self.repository.consolidated_fact(
            carrier_id=values["carrier_id"],
            jurisdiction=values["jurisdiction"],
            kind=values["kind"],
            subject_key=values["subject_key"],
        )
        now = datetime.now(UTC)
        if fact is None:
            fact = AgentMemoryFact(**values)
            self.repository.add_fact(fact)
            self.session.flush()
        else:
            fact.fact = values["fact"]
            fact.recurrence_count = values["recurrence_count"]
            fact.effective_at = values["effective_at"]
            fact.confirmation_count += 1
            fact.version += 1
            fact.active = True
            fact.updated_at = now
            self.session.add(fact)
        self.repository.add_version(
            AgentMemoryVersion(
                fact_id=fact.id,
                version=fact.version,
                actor_user_uuid=actor_user_uuid,
                proposal_id=proposal.id,
                decision_id=decision_id,
                trace_id=trace_id,
                **values,
            )
        )
        return fact.id

    def _validate(self, candidate: MemoryCandidate, jurisdiction: str) -> None:
        try:
            validate_memory_candidate(
                candidate,
                supplier=self.repository.supplier(str(candidate.carrier_id)),
                authenticated_jurisdiction=jurisdiction,
            )
        except MemoryValidationError as exc:
            raise AgentMemoryError(400, "Memory candidate is not eligible for storage.") from exc

    def _require_identical(self, existing: AgentMemoryDecision, decision: MemoryDecisionRequest) -> None:
        if existing.proposal_id != str(decision.proposal_id) or existing.action != decision.action:
            raise AgentMemoryError(409, "decision_id was already used for a different decision.")
        if decision.action == "edit":
            proposal = self.repository.get_proposal(existing.proposal_id)
            if proposal is None or decision.edited_candidate is None:
                raise AgentMemoryError(409, "decision_id was already used for a different decision.")
            if self._candidate_values(decision.edited_candidate) != self._proposal_values(proposal):
                raise AgentMemoryError(409, "decision_id was already used for a different decision.")

    @staticmethod
    def _require_decision_owner(
        existing: AgentMemoryDecision,
        conversation: AgentConversation,
        actor_user_uuid: str,
    ) -> None:
        if existing.conversation_id != conversation.id or existing.actor_user_uuid != actor_user_uuid:
            raise AgentMemoryError(404, "Memory decision not found.")

    @staticmethod
    def _candidate_values(candidate: MemoryCandidate) -> _CandidateValues:
        return {
            "carrier_id": str(candidate.carrier_id),
            "jurisdiction": candidate.jurisdiction,
            "kind": candidate.kind,
            "subject_key": candidate.subject_key,
            "fact": candidate.fact.strip(),
            "recurrence_count": candidate.recurrence_count,
            "effective_at": candidate.effective_at,
        }

    @staticmethod
    def _proposal_values(proposal: AgentMemoryProposal) -> _CandidateValues:
        return {
            "carrier_id": proposal.carrier_id,
            "jurisdiction": proposal.jurisdiction,
            "kind": proposal.kind,
            "subject_key": proposal.subject_key,
            "fact": proposal.fact,
            "recurrence_count": proposal.recurrence_count,
            "effective_at": proposal.effective_at,
        }

    @classmethod
    def _proposal_candidate(cls, proposal: AgentMemoryProposal) -> MemoryCandidate:
        return MemoryCandidate.model_validate(cls._proposal_values(proposal))
