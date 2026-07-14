"""Best-effort, off-request-path telemetry emission.

Emission runs in a Starlette ``BackgroundTask`` attached to the outgoing (error)
response, so it happens AFTER the HTTP response is sent — never on the business
request path — and any failure is logged and swallowed. Events can be lost on a
crash/restart before the task runs; these signals are best-effort diagnostics and
are never used as an exact KPI denominator.
"""

from __future__ import annotations

import logging

from sqlmodel import Session
from starlette.background import BackgroundTask

from ...core.config import Settings, get_settings
from ...db.session import get_engine
from . import events
from .models import TelemetryEvent

logger = logging.getLogger(__name__)

SERVICE_NAME = "central-api"


def _record(
    *,
    event: str,
    severity: str,
    warehouse: str | None,
    reason_code: str | None,
    value: int | None,
    properties: dict[str, object],
) -> None:
    """Insert one telemetry row in its own short-lived session; never raise."""
    try:
        settings = get_settings()
        if not settings.telemetry_enabled:
            return
        row = TelemetryEvent(
            event=event,
            category=events.CATEGORY_BY_EVENT.get(event, "operational"),
            service=SERVICE_NAME,
            env=settings.app_env,
            severity=severity,
            warehouse=warehouse,
            reason_code=reason_code,
            value=value,
            properties=events.allowed_properties(event, properties),
        )
        with Session(get_engine()) as session:
            session.add(row)
            session.commit()
    except Exception as exc:
        # Telemetry must never break the caller: log and swallow every failure.
        logger.warning("telemetry_emit_failed event=%s error_type=%s", event, type(exc).__name__)


def _enabled(settings: Settings | None = None) -> bool:
    return (settings or get_settings()).telemetry_enabled


def dispatch_rejection_task(
    *, warehouse: str, reason_code: str, quantity: int | None
) -> BackgroundTask | None:
    """Build a background task for a rejected dispatch, or None when disabled/invalid."""
    if not _enabled() or reason_code not in events.DISPATCH_REJECT_REASONS:
        return None
    properties: dict[str, object] = {"warehouse": warehouse, "reason_code": reason_code}
    if quantity is not None:
        properties["quantity"] = quantity
    return BackgroundTask(
        _record,
        event=events.DISPATCH_REJECTED,
        severity="warning",
        warehouse=warehouse,
        reason_code=reason_code,
        value=quantity,
        properties=properties,
    )


def record_dispatch_rejection(*, warehouse: str, reason_code: str, quantity: int | None) -> None:
    """Emit a real rejected-dispatch diagnostic synchronously (used off the HTTP path).

    The live operations feed calls this directly after catching an ``InventoryError``
    with a ``reject_event``, so genuinely rejected over-requests populate the same
    ``telemetry_events`` diagnostics the HTTP boundary produces. Honours ``TELEMETRY_ENABLED``
    and the reason-code allowlist, and never raises (``_record`` swallows all failures).
    """
    if not _enabled() or reason_code not in events.DISPATCH_REJECT_REASONS:
        return
    properties: dict[str, object] = {"warehouse": warehouse, "reason_code": reason_code}
    if quantity is not None:
        properties["quantity"] = quantity
    _record(
        event=events.DISPATCH_REJECTED,
        severity="warning",
        warehouse=warehouse,
        reason_code=reason_code,
        value=quantity,
        properties=properties,
    )


def access_denied_task(*, reason: str) -> BackgroundTask | None:
    """Build a background task for an API access denial, or None when disabled/invalid."""
    if not _enabled() or reason not in events.ACCESS_DENIED_REASONS:
        return None
    return BackgroundTask(
        _record,
        event=events.ACCESS_DENIED,
        severity="warning",
        warehouse=None,
        reason_code=reason,
        value=None,
        properties={"reason": reason},
    )
