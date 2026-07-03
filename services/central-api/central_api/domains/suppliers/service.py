"""Transactional supplier business rules with stable outward errors."""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from .models import Supplier
from .repository import SupplierRepository
from .schemas import RateUpdate, StatusUpdate, SupplierContact, SupplierCreate, SupplierPublic


class SupplierError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class SupplierService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = SupplierRepository(session)

    @staticmethod
    def public(row: Supplier) -> SupplierPublic:
        data = row.model_dump(exclude={"contact_email"})
        return SupplierPublic.model_validate(
            {**data, "has_contact_email": bool(row.contact_email and row.contact_email.strip())}
        )

    def create(
        self, payload: SupplierCreate, *, supplier_id: str | None = None, rate_updated_at: datetime | None = None
    ) -> SupplierPublic:
        if self.repository.find_identity(payload.name, payload.country):
            raise SupplierError(409, "A supplier with that name and country already exists")
        values = payload.model_dump()
        if supplier_id:
            values["id"] = supplier_id
        if rate_updated_at:
            values["rate_updated_at"] = rate_updated_at
        row = Supplier(**values)
        self.repository.add(row)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise SupplierError(409, "A supplier with that name and country already exists") from exc
        self.session.refresh(row)
        return self.public(row)

    def list(self, country: str | None, category: str | None) -> list[SupplierPublic]:
        return [self.public(row) for row in self.repository.list(country, category)]

    def require(self, supplier_id: str) -> Supplier:
        row = self.repository.get(supplier_id)
        if row is None:
            raise SupplierError(404, "Supplier not found")
        return row

    def get(self, supplier_id: str) -> SupplierPublic:
        return self.public(self.require(supplier_id))

    def contact(self, supplier_id: str) -> SupplierContact:
        row = self.require(supplier_id)
        return SupplierContact(id=row.id, contact_email=row.contact_email)

    def update_rate(self, supplier_id: str, payload: RateUpdate) -> SupplierPublic:
        row = self.require(supplier_id)
        row.rate_per_shipment = payload.rate_per_shipment
        row.rate_updated_at = datetime.now(UTC)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return self.public(row)

    def update_status(self, supplier_id: str, payload: StatusUpdate) -> SupplierPublic:
        row = self.require(supplier_id)
        row.status = payload.status
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return self.public(row)

    def delete(self, supplier_id: str) -> None:
        self.repository.delete(self.require(supplier_id))
        self.session.commit()
