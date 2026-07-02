"""Idempotent local seed command for Engagement 5 inventory fixtures."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from ...core.config import get_settings
from ...db.session import get_engine
from .models import SKU, StockEntry, StockExit
from .repository import entry_table, exit_table, sku_table

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SKUSeed:
    name: str
    sku: str
    client_name: str
    category: str
    warehouse: str


@dataclass(frozen=True)
class EntrySeed:
    sku: str
    warehouse: str
    quantity: int
    reference: str
    created_at: datetime


@dataclass(frozen=True)
class ExitSeed:
    sku: str
    warehouse: str
    quantity: int
    exit_type: str
    tracking_number: str | None
    created_at: datetime


SKU_SEEDS = (
    SKUSeed("Classic White Sneaker - Size 42", "CLT-SNK-W-42", "PureStep Footwear", "fashion", "LA"),
    SKUSeed("Classic White Sneaker - Size 42", "CLT-SNK-W-42-Z", "PureStep Footwear", "fashion", "ZGZ"),
    SKUSeed("Wireless Earbuds Pro", "TEC-EAR-001", "SoundWave Electronics", "electronics", "LA"),
    SKUSeed("Hydrating Face Serum 30ml", "CSM-SRM-030", "GlowLab Cosmetics", "cosmetics", "ZGZ"),
    SKUSeed("Slim Fit Chino - Navy 32/32", "CLT-CHN-N-32", "UrbanThread", "fashion", "LA"),
    SKUSeed("USB-C Fast Charger 65W", "TEC-CHG-065", "SoundWave Electronics", "electronics", "ZGZ"),
)

ENTRY_SEEDS = (
    EntrySeed("CLT-SNK-W-42", "LA", 50, "PO-2024-0098", datetime(2024, 6, 3, 14, 0, tzinfo=UTC)),
    EntrySeed("CLT-SNK-W-42", "LA", 25, "GR-LA-0234", datetime(2024, 6, 10, 16, 30, tzinfo=UTC)),
    EntrySeed("CLT-SNK-W-42-Z", "ZGZ", 40, "PO-2024-0112", datetime(2024, 6, 5, 9, 0, tzinfo=UTC)),
    EntrySeed("TEC-EAR-001", "LA", 30, "GR-LA-0241", datetime(2024, 6, 7, 11, 15, tzinfo=UTC)),
)

EXIT_SEEDS = (
    ExitSeed(
        "CLT-SNK-W-42",
        "LA",
        10,
        "dispatch",
        "1Z999AA10123456784",
        datetime(2024, 6, 12, 15, 0, tzinfo=UTC),
    ),
    ExitSeed("CLT-SNK-W-42", "LA", 2, "loss", None, datetime(2024, 6, 13, 17, 45, tzinfo=UTC)),
    ExitSeed(
        "CLT-SNK-W-42-Z",
        "ZGZ",
        5,
        "dispatch",
        "ES1234567890",
        datetime(2024, 6, 14, 10, 20, tzinfo=UTC),
    ),
)


class SeedConfigurationError(ValueError):
    """Raised before database access when the Identity reference is unusable."""


class SeedConflictError(ValueError):
    """Raised when a natural seed identity already exists with different data."""


def seed_user_uuid() -> str:
    """Require a canonical UUID while leaving Identity as the sole user-data owner."""
    raw = (get_settings().seed_user_uuid or "").strip()
    if not raw:
        raise SeedConfigurationError("SEED_USER_UUID is required")
    try:
        parsed = UUID(raw)
    except ValueError as exc:
        raise SeedConfigurationError("SEED_USER_UUID must be a valid UUID") from exc
    return str(parsed)


def _find_sku(session: Session, sku: str, warehouse: str, *, lock: bool = False) -> SKU | None:
    statement = select(SKU).where(sku_table.c.sku == sku, sku_table.c.warehouse == warehouse)
    if lock:
        statement = statement.with_for_update()
    return session.execute(statement).scalar_one_or_none()


def _sku_id(sku: SKU) -> int:
    if sku.id is None:
        raise RuntimeError("Seeded SKU is missing its primary key")
    return sku.id


def _ensure_skus(session: Session) -> dict[tuple[str, str], SKU]:
    """Insert missing SKUs and refuse to overwrite a conflicting existing row."""
    result: dict[tuple[str, str], SKU] = {}
    for item in SKU_SEEDS:
        existing = _find_sku(session, item.sku, item.warehouse)
        expected = {
            "name": item.name,
            "client_name": item.client_name,
            "category": item.category,
        }
        if existing is not None:
            actual = {key: getattr(existing, key) for key in expected}
            if actual != expected:
                raise SeedConflictError(f"Seed SKU '{item.sku}' in '{item.warehouse}' conflicts with existing data")
            result[(item.sku, item.warehouse)] = existing
            continue
        created = SKU(
            name=item.name,
            sku=item.sku,
            client_name=item.client_name,
            category=item.category,
            warehouse=item.warehouse,
        )
        session.add(created)
        session.flush()
        result[(item.sku, item.warehouse)] = created
    return result


def _ensure_entries(session: Session, skus: dict[tuple[str, str], SKU], user_uuid: str) -> None:
    """Use reference plus fixed timestamp as a repeatable inbound identity."""
    for item in ENTRY_SEEDS:
        sku_id = _sku_id(skus[(item.sku, item.warehouse)])
        existing = session.execute(
            select(StockEntry).where(
                entry_table.c.sku_id == sku_id,
                entry_table.c.warehouse == item.warehouse,
                entry_table.c.reference == item.reference,
                entry_table.c.created_at == item.created_at,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.quantity != item.quantity:
                raise SeedConflictError(f"Seed entry '{item.reference}' conflicts with existing data")
            continue
        session.add(
            StockEntry(
                sku_id=sku_id,
                quantity=item.quantity,
                reference=item.reference,
                warehouse=item.warehouse,
                created_at=item.created_at,
                user_uuid=user_uuid,
            )
        )
    session.flush()


def _ensure_exits(session: Session, skus: dict[tuple[str, str], SKU], user_uuid: str) -> None:
    """Lock each SKU before checking stock and inserting a missing outbound row."""
    for item in EXIT_SEEDS:
        seeded_sku = skus[(item.sku, item.warehouse)]
        sku_id = _sku_id(seeded_sku)
        _find_sku(session, item.sku, item.warehouse, lock=True)
        existing = session.execute(
            select(StockExit).where(
                exit_table.c.sku_id == sku_id,
                exit_table.c.warehouse == item.warehouse,
                exit_table.c.created_at == item.created_at,
            )
        ).scalar_one_or_none()
        if existing is not None:
            if (
                existing.quantity != item.quantity
                or existing.exit_type != item.exit_type
                or existing.tracking_number != item.tracking_number
            ):
                raise SeedConflictError(f"Seed exit for '{item.sku}' conflicts with existing data")
            continue
        # Entry seeds are flushed first, so this transaction sees the available balance.
        received = int(
            session.scalar(
                select(func.coalesce(func.sum(entry_table.c.quantity), 0))
                .where(entry_table.c.sku_id == sku_id, entry_table.c.warehouse == item.warehouse)
            )
            or 0
        )
        prior_exits = int(
            session.scalar(
                select(func.coalesce(func.sum(exit_table.c.quantity), 0))
                .where(exit_table.c.sku_id == sku_id, exit_table.c.warehouse == item.warehouse)
            )
            or 0
        )
        if item.quantity > received - prior_exits:
            raise SeedConflictError(f"Seed exit for '{item.sku}' would make stock negative")
        session.add(
            StockExit(
                sku_id=sku_id,
                quantity=item.quantity,
                exit_type=item.exit_type,
                tracking_number=item.tracking_number,
                warehouse=item.warehouse,
                created_at=item.created_at,
                user_uuid=user_uuid,
            )
        )
        session.flush()


def seed_inventory(session: Session, user_uuid: str) -> None:
    """Seed the complete fixture atomically so retries never leave partial data."""
    try:
        skus = _ensure_skus(session)
        _ensure_entries(session, skus, user_uuid)
        _ensure_exits(session, skus, user_uuid)
        session.commit()
    except (SQLAlchemyError, SeedConflictError):
        session.rollback()
        raise


def entrypoint() -> None:
    """Run the local seed with safe, non-payload diagnostics."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        user_uuid = seed_user_uuid()
        with Session(get_engine()) as session:
            seed_inventory(session, user_uuid)
    except (SeedConfigurationError, SeedConflictError) as exc:
        logger.error("inventory_seed_rejected reason=%s", type(exc).__name__)
        raise SystemExit(str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("inventory_seed_database_failure error_type=%s", type(exc).__name__)
        raise SystemExit("Inventory seed failed because the database is unavailable") from exc
    logger.info("inventory_seed_complete")
