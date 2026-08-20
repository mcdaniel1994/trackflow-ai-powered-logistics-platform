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

    def get(self, ticket_id: str) -> RfpTicket | None:
        """Unscoped fetch for the background intake runner, which owns the id it just created."""
        return self.session.get(RfpTicket, ticket_id)

    def add_ticket(self, ticket: RfpTicket) -> RfpTicket:
        self.session.add(ticket)
        self.session.commit()
        self.session.refresh(ticket)
        return ticket

    def delete_ticket(self, ticket: RfpTicket) -> None:
        """Compensate a failed broker publication so no analyzing orphan remains."""
        self.session.delete(ticket)
        self.session.commit()

    def save(self, ticket: RfpTicket) -> RfpTicket:
        self.session.add(ticket)
        self.session.commit()
        self.session.refresh(ticket)
        return ticket

    def add_sections(self, sections: list[RfpDepartmentSection]) -> None:
        for section in sections:
            self.session.add(section)
        self.session.commit()

    def save_section(self, section: RfpDepartmentSection) -> RfpDepartmentSection:
        self.session.add(section)
        self.session.commit()
        self.session.refresh(section)
        return section

    def section_for_department(self, ticket_id: str, department_id: str) -> RfpDepartmentSection | None:
        statement = select(RfpDepartmentSection).where(
            RfpDepartmentSection.ticket_id == ticket_id,
            RfpDepartmentSection.department_id == department_id,
        )
        return self.session.exec(statement).one_or_none()

    def add_final_document(self, document: RfpFinalDocument) -> RfpFinalDocument:
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document
