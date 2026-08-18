"""Cookie-authenticated real-time transport endpoints."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ...core.config import Settings, get_settings
from .auth import RealtimePrincipal, authenticate_http_stream
from .bus import RealtimeBus, SubscriptionClosed, rfp_ticket_topic
from .schemas import RealtimeEvent

router = APIRouter(prefix="/realtime", tags=["realtime"])

SSE_KEEPALIVE_SECONDS = 15.0


def encode_sse_event(event: RealtimeEvent) -> bytes:
    """Encode one event using the SSE field names required by the Part 1 contract."""
    data = json.dumps(event.data, separators=(",", ":"), ensure_ascii=False)
    return f"id: {event.event_id}\nevent: {event.event}\ndata: {data}\n\n".encode()


async def stream_rfp_events(
    bus: RealtimeBus,
    auth: RealtimePrincipal,
    *,
    keepalive_seconds: float = SSE_KEEPALIVE_SECONDS,
) -> AsyncIterator[bytes]:
    """Yield owner-only events and close no later than access-token expiry."""
    topic = rfp_ticket_topic(auth.principal.user_id)
    async with bus.subscribe(topic) as subscription:
        yield b": connected\n\n"
        while True:
            seconds_to_expiry = (auth.expires_at - datetime.now(UTC)).total_seconds()
            if seconds_to_expiry <= 0:
                return
            timeout = min(keepalive_seconds, seconds_to_expiry)
            try:
                event = await asyncio.wait_for(subscription.receive(), timeout=timeout)
            except TimeoutError:
                if datetime.now(UTC) >= auth.expires_at:
                    return
                yield b": keep-alive\n\n"
            except SubscriptionClosed:
                return
            else:
                yield encode_sse_event(event)


def get_realtime_bus(request: Request) -> RealtimeBus:
    """Return the application-scoped bus configured by the app factory."""
    bus = getattr(request.app.state, "realtime_bus", None)
    if not isinstance(bus, RealtimeBus):
        raise RuntimeError("Realtime bus is not configured")
    return bus


@router.get("/rfp/stream")
async def rfp_ticket_stream(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    bus: Annotated[RealtimeBus, Depends(get_realtime_bus)],
) -> StreamingResponse:
    """Stream model-free RFP ticket-created notifications for the authenticated owner."""
    if not settings.rfp_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The RFP workflow is not available right now.",
        )
    auth = authenticate_http_stream(request, settings)
    return StreamingResponse(
        stream_rfp_events(bus, auth),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
