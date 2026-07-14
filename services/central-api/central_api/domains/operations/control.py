"""Read/write helpers for the single-row operations-feed kill switch."""

from __future__ import annotations

from sqlmodel import Session

from .models import CONTROL_ROW_ID, OperationsFeedControl, utc_now


def _row(session: Session) -> OperationsFeedControl:
    """Return the singleton control row, creating it (enabled) if absent."""
    row = session.get(OperationsFeedControl, CONTROL_ROW_ID)
    if row is None:
        row = OperationsFeedControl(id=CONTROL_ROW_ID, enabled=True, note="auto-created")
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def feed_enabled(session: Session) -> bool:
    """Whether the live operations feed is currently permitted to write."""
    return bool(_row(session).enabled)


def set_feed_enabled(session: Session, *, enabled: bool, note: str | None = None) -> None:
    """Flip the runtime kill switch without a redeploy; committed immediately."""
    row = _row(session)
    row.enabled = enabled
    row.note = note
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
