"""Deterministic synthetic incidents so the Back Office dashboard reads as active.

Production incidents start empty on purpose: the legacy importer (`seed.py`) reads
a CSV of real customer reports and is barred from production. This seeder invents
its own data instead, covering every status, category, origin, and branch so the
summary tiles and filters have something meaningful to show.

Rows are written straight through `IncidentRepository.add()` rather than
`IncidentService.create()`. That is the sanctioned bulk path, and it is the only
one that can express this data at all: the service forces `status=open` and
`IncidentCreate` has no status field, so a service-mediated seed could only ever
produce a wall of identical open incidents with today's timestamp. The database
CHECK constraints remain the backstop for the direct insert.

Generation is seeded from a fixed constant, so a rerun against an empty database
produces byte-identical rows. That makes the seeder safe to reason about and lets
tests assert determinism rather than merely "some rows appeared".
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from trackflow_incidents import Branch, IncidentCategory, IncidentOrigin, IncidentStatus

from ...db.session import get_engine
from .models import Incident
from .repository import IncidentRepository

logger = logging.getLogger(__name__)

# Fixed so reruns are identical. Changing it rewrites the whole demo data set.
RANDOM_SEED = 20260820
INCIDENT_COUNT = 45
HISTORY_DAYS = 30

# Above this, the dashboard already has data -- real, previously seeded, or
# imported -- and this seeder must not add to it.
EXISTING_INCIDENT_THRESHOLD = 10

# Namespaced away from the legacy importer's sha256(incident_id) so the two can
# never collide on uq_incidents_import_key_hash, and so demo rows stay
# identifiable in the database.
IMPORT_KEY_NAMESPACE = "demo-incident:"


class DemoSeedError(RuntimeError):
    """The demo seed could not be written."""


@dataclass(frozen=True)
class DemoSeedResult:
    """What one run did, for logging and tests."""

    existing: int
    inserted: int
    skipped: bool


@dataclass(frozen=True)
class _Template:
    """One realistic incident shape for a category."""

    category: IncidentCategory
    title: str
    description: str
    origins: tuple[IncidentOrigin, ...]
    branches: tuple[Branch, ...]


_ALL_BRANCHES = tuple(Branch)
_WAREHOUSES = (Branch.LA_WAREHOUSE, Branch.ZARAGOZA_WAREHOUSE)
_OFFICES = (Branch.LA_OFFICE, Branch.ZARAGOZA_OFFICE, Branch.CENTRAL)

# Each template pins the origins and branches that make sense for it: a warehouse
# incident cannot originate from a customer, and a client complaint does not come
# from a warehouse floor. Distribution realism matters more than volume here --
# the dashboard is judged on whether it looks plausible.
_TEMPLATES: tuple[_Template, ...] = (
    _Template(
        IncidentCategory.LOST_PARCEL,
        "Parcel {ref} not scanned at final hub",
        "Tracking for parcel {ref} stopped after the regional hub scan on {date}. "
        "The carrier has opened a trace and the client has been notified.",
        (IncidentOrigin.CUSTOMER, IncidentOrigin.BRANCH),
        _ALL_BRANCHES,
    ),
    _Template(
        IncidentCategory.DELIVERY_FAILURE,
        "Failed delivery attempt for order {ref}",
        "Order {ref} failed delivery on {date} after two attempts at the recipient address. "
        "Awaiting updated delivery instructions before the next attempt.",
        (IncidentOrigin.CUSTOMER, IncidentOrigin.BRANCH),
        _ALL_BRANCHES,
    ),
    _Template(
        IncidentCategory.INVENTORY_DISCREPANCY,
        "Cycle count variance on SKU {ref}",
        "A cycle count on {date} found a variance of {qty} units for SKU {ref}. "
        "Recount scheduled and the ledger entry has been flagged for review.",
        (IncidentOrigin.INTERNAL, IncidentOrigin.BRANCH),
        _WAREHOUSES,
    ),
    _Template(
        IncidentCategory.CARRIER_ISSUE,
        "Carrier pickup missed at {branch_label}",
        "The scheduled carrier pickup on {date} did not take place, delaying {qty} outbound "
        "shipments by one working day. Carrier account manager has been contacted.",
        (IncidentOrigin.BRANCH, IncidentOrigin.INTERNAL),
        _ALL_BRANCHES,
    ),
    _Template(
        IncidentCategory.RETURNS_ISSUE,
        "Return {ref} received without documentation",
        "Return {ref} arrived on {date} with no RMA paperwork, so it could not be matched to an "
        "order. Held in the returns cage pending client confirmation.",
        (IncidentOrigin.CUSTOMER, IncidentOrigin.INTERNAL),
        _WAREHOUSES,
    ),
    _Template(
        IncidentCategory.WAREHOUSE_INCIDENT,
        "Aisle {aisle} blocked after pallet shift",
        "A pallet shifted in aisle {aisle} on {date}, blocking picking access. No injuries. "
        "The aisle was cordoned off and restocked the same shift.",
        (IncidentOrigin.INTERNAL,),
        _WAREHOUSES,
    ),
    _Template(
        IncidentCategory.SYSTEM_FAILURE,
        "Barcode scanning outage at {branch_label}",
        "Barcode scanning was unavailable for {qty} minutes on {date}, forcing a manual "
        "fallback process. The failed network switch has been replaced.",
        (IncidentOrigin.INTERNAL,),
        _ALL_BRANCHES,
    ),
    _Template(
        IncidentCategory.CLIENT_COMPLAINT,
        "Client escalation regarding order {ref}",
        "The client escalated on {date} citing repeated delays on order {ref}. "
        "Account management has scheduled a service review.",
        (IncidentOrigin.CUSTOMER,),
        _OFFICES,
    ),
    _Template(
        IncidentCategory.OTHER,
        "Access badge fault at {branch_label}",
        "A badge reader intermittently denied access on {date}, delaying shift start by "
        "{qty} minutes. Facilities replaced the reader.",
        (IncidentOrigin.INTERNAL, IncidentOrigin.BRANCH),
        _ALL_BRANCHES,
    ),
)

_BRANCH_LABELS: dict[Branch, str] = {
    Branch.CENTRAL: "Central",
    Branch.LA_WAREHOUSE: "Los Angeles - Warehouse",
    Branch.LA_OFFICE: "Los Angeles - Office",
    Branch.ZARAGOZA_WAREHOUSE: "Zaragoza - Warehouse",
    Branch.ZARAGOZA_OFFICE: "Zaragoza - Office",
}

# Older incidents are far more likely to have reached a terminal state, which is
# what makes the dashboard's status mix look like a real operation rather than a
# uniform sample.
_RECENT_STATUS_WEIGHTS: tuple[tuple[IncidentStatus, int], ...] = (
    (IncidentStatus.OPEN, 6),
    (IncidentStatus.IN_PROGRESS, 3),
    (IncidentStatus.RESOLVED, 1),
    (IncidentStatus.DISCARDED, 1),
)
_AGED_STATUS_WEIGHTS: tuple[tuple[IncidentStatus, int], ...] = (
    (IncidentStatus.OPEN, 1),
    (IncidentStatus.IN_PROGRESS, 2),
    (IncidentStatus.RESOLVED, 8),
    (IncidentStatus.DISCARDED, 1),
)
RECENT_CUTOFF_DAYS = 7


def _import_key(slug: str) -> str:
    return hashlib.sha256(f"{IMPORT_KEY_NAMESPACE}{slug}".encode()).hexdigest()


def _weighted_status(
    rng: random.Random, weights: tuple[tuple[IncidentStatus, int], ...]
) -> IncidentStatus:
    population = [status for status, weight in weights for _ in range(weight)]
    return rng.choice(population)


def _resolution_delay(rng: random.Random, status: IncidentStatus) -> timedelta:
    """How long after creation the row was last touched.

    An open incident has never been updated, so its timestamps match; anything
    else moved at least once, and terminal states took longer to get there.
    """
    if status is IncidentStatus.OPEN:
        return timedelta(0)
    if status is IncidentStatus.IN_PROGRESS:
        return timedelta(hours=rng.randint(2, 36))
    return timedelta(hours=rng.randint(12, 120))


def build_demo_incidents(now: datetime, user_uuid: str | None) -> list[Incident]:
    """Generate the full demo set. Pure apart from the fixed-seed RNG."""
    rng = random.Random(RANDOM_SEED)
    incidents: list[Incident] = []

    for index in range(INCIDENT_COUNT):
        # Cycle templates so every category is guaranteed, rather than trusting a
        # random draw to cover all nine across only 45 rows.
        template = _TEMPLATES[index % len(_TEMPLATES)]
        branch = _ALL_BRANCHES[index % len(_ALL_BRANCHES)]
        if branch not in template.branches:
            branch = rng.choice(template.branches)
        origin = rng.choice(template.origins)

        age_hours = rng.randint(1, HISTORY_DAYS * 24 - 1)
        created_at = now - timedelta(hours=age_hours)
        weights = (
            _RECENT_STATUS_WEIGHTS
            if age_hours <= RECENT_CUTOFF_DAYS * 24
            else _AGED_STATUS_WEIGHTS
        )
        status = _weighted_status(rng, weights)
        updated_at = min(created_at + _resolution_delay(rng, status), now)

        reference = f"{rng.randint(100000, 999999)}"
        fields = {
            "ref": reference,
            "date": created_at.strftime("%d %b %Y"),
            "qty": rng.randint(2, 45),
            "branch_label": _BRANCH_LABELS[branch],
            "aisle": f"{rng.choice('ABCDEF')}-{rng.randint(1, 24):02d}",
        }
        incidents.append(
            Incident(
                title=template.title.format(**fields)[:200],
                description=template.description.format(**fields),
                category=template.category.value,
                status=status.value,
                origin=origin.value,
                branch=branch.value,
                created_at=created_at,
                updated_at=updated_at,
                created_by_user_uuid=user_uuid,
                import_key_hash=_import_key(f"{index}:{reference}"),
            )
        )
    return incidents


def seed_demo_incidents(
    session: Session,
    *,
    now: datetime | None = None,
    user_uuid: str | None = None,
) -> DemoSeedResult:
    """Insert the demo set unless the table already holds real data.

    The whole set lands in one transaction: a half-seeded dashboard is worse than
    an empty one, and a partial run would also leave the count guard in a state
    that blocks the retry.
    """
    repository = IncidentRepository(session)
    existing = repository.count()
    if existing > EXISTING_INCIDENT_THRESHOLD:
        logger.info(
            "demo_incident_seed_skipped existing=%s threshold=%s",
            existing,
            EXISTING_INCIDENT_THRESHOLD,
        )
        return DemoSeedResult(existing=existing, inserted=0, skipped=True)

    incidents = build_demo_incidents(now or datetime.now(UTC), user_uuid)
    try:
        for incident in incidents:
            repository.add(incident)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        # Never surface the driver message: it can carry row values.
        logger.error("demo_incident_seed_failed error_type=%s", type(exc).__name__)
        raise DemoSeedError("demo incident seed failed") from None

    logger.info("demo_incident_seed_complete existing=%s inserted=%s", existing, len(incidents))
    return DemoSeedResult(existing=existing, inserted=len(incidents), skipped=False)


def entrypoint() -> None:
    """Console-script entry: `seed-demo-incidents`."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    # Attribution is optional. When set, delegated OAuth principals can see these
    # rows; `_authorize_delegated` scopes non-admin reads to their own incidents.
    user_uuid = os.environ.get("SEED_USER_UUID", "").strip() or None
    with Session(get_engine()) as session:
        seed_demo_incidents(session, user_uuid=user_uuid)
