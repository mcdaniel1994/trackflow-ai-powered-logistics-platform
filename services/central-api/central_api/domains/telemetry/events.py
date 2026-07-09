"""Server-owned telemetry event registry and property allowlists.

The single source of truth for which best-effort diagnostic events exist and which
property keys each one may carry. Emission drops any key not on the allowlist before
insert, so PII-prone or unexpected fields can never reach the store.
"""

from __future__ import annotations

# Event names (stable, dot-namespaced, describe an outcome — never embed values).
DISPATCH_REJECTED = "inventory.dispatch.rejected"
ACCESS_DENIED = "api.access.denied"

# Categories drive retention (operational = short, security = risk-based).
CATEGORY_BY_EVENT: dict[str, str] = {
    DISPATCH_REJECTED: "operational",
    ACCESS_DENIED: "security",
}

# Allowlisted property keys per event. Only these keys survive to storage.
PROPERTY_ALLOWLIST: dict[str, frozenset[str]] = {
    DISPATCH_REJECTED: frozenset({"warehouse", "reason_code", "quantity"}),
    ACCESS_DENIED: frozenset({"reason"}),
}

# Safe, bounded reason codes for a rejected dispatch attempt.
DISPATCH_REJECT_REASONS: frozenset[str] = frozenset(
    {"INSUFFICIENT_STOCK", "SKU_NOT_FOUND", "WAREHOUSE_MISMATCH"}
)

# Access-denial reasons limited to what the shared verifier actually distinguishes
# without weakening its non-enumerating 401 response.
ACCESS_DENIED_REASONS: frozenset[str] = frozenset(
    {"unauthenticated", "csrf", "password_change_required"}
)


def allowed_properties(event: str, properties: dict[str, object]) -> dict[str, object]:
    """Return only the allowlisted keys for ``event``; unknown keys are dropped."""
    allowed = PROPERTY_ALLOWLIST.get(event, frozenset())
    return {key: value for key, value in properties.items() if key in allowed}
