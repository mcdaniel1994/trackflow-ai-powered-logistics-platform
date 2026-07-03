"""Bounded supplier queries and explicit persistence operations."""

from sqlalchemy import func
from sqlmodel import Session, select

from .models import Supplier


class SupplierRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, supplier: Supplier) -> None:
        self.session.add(supplier)

    def get(self, supplier_id: str) -> Supplier | None:
        return self.session.get(Supplier, supplier_id)

    def find_identity(self, name: str, country: str) -> Supplier | None:
        return self.session.exec(
            select(Supplier).where(func.lower(Supplier.name) == name.strip().casefold(), Supplier.country == country)
        ).one_or_none()

    def list(self, country: str | None, category: str | None) -> list[Supplier]:
        statement = select(Supplier)
        if country:
            statement = statement.where(Supplier.country == country)
        rows = list(self.session.exec(statement.order_by(Supplier.country, Supplier.name)).all())
        return [row for row in rows if category is None or category in row.categories]

    def delete(self, supplier: Supplier) -> None:
        self.session.delete(supplier)
