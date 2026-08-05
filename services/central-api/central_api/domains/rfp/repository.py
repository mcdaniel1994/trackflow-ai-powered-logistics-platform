"""Persistence access for RFP tickets, sections, and final documents.

Owner-scoped reads only: a ticket is visible to the user who owns it. The service layer enforces
authorization; this layer never widens it.
"""

from __future__ import annotations

from sqlmodel import Session, select

from .models import RfpDepartmentSection, RfpFinalDocument, RfpTicket


class RfpRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_owner(
        self,
        owner_user_uuid: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[RfpTicket]:
        statement = select(RfpTicket).where(RfpTicket.owner_user_uuid == owner_user_uuid)
        if status is not None:
            statement = statement.where(RfpTicket.status == status)
        statement = statement.order_by(RfpTicket.updated_at.desc()).limit(limit)  # type: ignore[attr-defined]
        return list(self.session.exec(statement).all())

    def get_for_owner(self, ticket_id: str, owner_user_uuid: str) -> RfpTicket | None:
        statement = select(RfpTicket).where(
            RfpTicket.id == ticket_id,
            RfpTicket.owner_user_uuid == owner_user_uuid,
        )
        return self.session.exec(statement).one_or_none()

    def sections_for_ticket(self, ticket_id: str) -> list[RfpDepartmentSection]:
        statement = (
            select(RfpDepartmentSection)
            .where(RfpDepartmentSection.ticket_id == ticket_id)
            .order_by(RfpDepartmentSection.department_id)  # type: ignore[arg-type]
        )
        return list(self.session.exec(statement).all())

    def final_document(self, ticket_id: str) -> RfpFinalDocument | None:
        statement = select(RfpFinalDocument).where(RfpFinalDocument.ticket_id == ticket_id)
        return self.session.exec(statement).one_or_none()

    def add_ticket(self, ticket: RfpTicket) -> RfpTicket:
        self.session.add(ticket)
        self.session.commit()
        self.session.refresh(ticket)
        return ticket
