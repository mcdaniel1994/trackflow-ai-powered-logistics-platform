"""Deterministic conversion from legacy rows into the Central API contract."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from .contracts import Branch, IncidentCategory, IncidentOrigin, IncidentStatus
from .legacy import LegacyIncidentRow

CATEGORY_MAP = {
    "LOST_PARCEL": IncidentCategory.LOST_PARCEL,
    "DELAYED_DELIVERY": IncidentCategory.DELIVERY_FAILURE,
    "WRONG_ADDRESS": IncidentCategory.DELIVERY_FAILURE,
    "RETURN_REQUEST": IncidentCategory.RETURNS_ISSUE,
    "DAMAGE": IncidentCategory.CARRIER_ISSUE,
}
STATUS_MAP = {
    "OPEN": IncidentStatus.OPEN,
    "CLOSED": IncidentStatus.RESOLVED,
    "DISCARDED": IncidentStatus.DISCARDED,
}


@dataclass(frozen=True)
class NormalizedIncident:
    title: str
    description: str
    category: IncidentCategory
    status: IncidentStatus
    origin: IncidentOrigin
    branch: Branch
    created_at: datetime
    updated_at: datetime
    import_key_hash: str


def normalize_legacy_incident(row: LegacyIncidentRow) -> NormalizedIncident:
    category = CATEGORY_MAP[row.category]
    created_at = datetime.fromisoformat(row.date).replace(tzinfo=UTC)
    description = row.description.strip()
    title_fragment = description.split(".", maxsplit=1)[0].strip()[:120]
    title = title_fragment if len(title_fragment) >= 5 else f"Historical {category.value.replace('_', ' ')} incident"
    return NormalizedIncident(
        title=title,
        description=description,
        category=category,
        status=STATUS_MAP[row.status],
        origin=IncidentOrigin.CUSTOMER,
        branch=Branch.CENTRAL,
        created_at=created_at,
        updated_at=created_at,
        import_key_hash=sha256(row.incident_id.encode("utf-8")).hexdigest(),
    )

