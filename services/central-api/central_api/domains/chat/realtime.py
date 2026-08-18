"""Owner-scoped WebSocket transport for persisted first-line CX chat."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException, status
from pydantic import ValidationError

from ...core.config import Settings, get_settings
from ..agents.config import is_agents_configured
from ..realtime.auth import RealtimePrincipal, authenticate_websocket_upgrade
from ..realtime.bus import (
    RealtimeBus,
    RealtimeSubscription,
    SubscriptionClosed,
    chat_session_topic,
)
from .schemas import ChatInterruptData, ChatUserMessageData
from .streaming import ChatGenerationManager, session_snapshot

router = APIRouter(prefix="/realtime", tags=["realtime-chat"])


def _websocket_bus(websocket: WebSocket) -> RealtimeBus:
    bus = getattr(websocket.app.state, "realtime_bus", None)
    if not isinstance(bus, RealtimeBus):
        raise RuntimeError("Realtime bus is not configured")
    return bus


def _chat_manager(websocket: WebSocket) -> ChatGenerationManager:
    manager = getattr(websocket.app.state, "chat_generation_manager", None)
    if not isinstance(manager, ChatGenerationManager):
        raise RuntimeError("Chat generation manager is not configured")
    return manager


async def _send_chat_events(websocket: WebSocket, subscription: RealtimeSubscription) -> None:
    while True:
        try:
            event = await subscription.receive()
        except SubscriptionClosed:
            return
        await websocket.send_json({"event": event.event, "data": event.data})


async def _receive_chat_events(
    websocket: WebSocket,
    *,
    settings: Settings,
    manager: ChatGenerationManager,
    bus: RealtimeBus,
    session_id: str,
    owner_user_id: str,
    source_access_token: str,
) -> None:
    topic = chat_session_topic(session_id)
    while True:
        frame = await websocket.receive_json()
        if not isinstance(frame, dict) or not isinstance(frame.get("event"), str):
            bus.publish(topic, "generation_failed", {"session_id": session_id, "detail": "Invalid chat event."})
            continue
        event_name = frame["event"]
        data = frame.get("data")
        try:
            if event_name == "user_message":
                user_payload = ChatUserMessageData.model_validate(data)
                if user_payload.session_id != session_id:
                    raise ValueError("session mismatch")
                started = await manager.start(
                    settings=settings,
                    session_id=session_id,
                    owner_user_id=owner_user_id,
                    source_access_token=source_access_token,
                    question=user_payload.text,
                    route=user_payload.route,
                )
                if not started:
                    bus.publish(
                        topic,
                        "generation_failed",
                        {"session_id": session_id, "detail": "A response is already in progress."},
                    )
            elif event_name == "interrupt_requested":
                interrupt_payload = ChatInterruptData.model_validate(data)
                if interrupt_payload.session_id != session_id:
                    raise ValueError("session mismatch")
                interrupted = await manager.interrupt(
                    settings=settings,
                    session_id=session_id,
                    owner_user_id=owner_user_id,
                    source_access_token=source_access_token,
                    new_input=interrupt_payload.new_input,
                    route=interrupt_payload.route,
                )
                if not interrupted:
                    bus.publish(
                        topic,
                        "generation_failed",
                        {"session_id": session_id, "detail": "No response is in progress."},
                    )
            else:
                raise ValueError("unsupported event")
        except (ValidationError, ValueError):
            bus.publish(topic, "generation_failed", {"session_id": session_id, "detail": "Invalid chat event."})


async def _close_at_expiry(websocket: WebSocket, auth: RealtimePrincipal) -> None:
    delay = max(0.0, (auth.expires_at - datetime.now(UTC)).total_seconds())
    await asyncio.sleep(delay)
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Connection expired")


@router.websocket("/chat/{session_id}")
async def chat_socket(
    websocket: WebSocket,
    session_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Bind one cookie-authenticated socket to one owner-scoped persisted conversation."""
    if not is_agents_configured(settings):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Connection rejected")
    auth = authenticate_websocket_upgrade(websocket, settings)
    owner_user_id = auth.principal.user_id
    if await asyncio.to_thread(session_snapshot, session_id, owner_user_id) is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Connection rejected")
    bus = _websocket_bus(websocket)
    manager = _chat_manager(websocket)
    topic = chat_session_topic(session_id)
    source_access_token = websocket.cookies.get(settings.auth_config.access_cookie_name, "")

    async with bus.subscribe(topic) as subscription:
        snapshot = await asyncio.to_thread(session_snapshot, session_id, owner_user_id)
        if snapshot is None:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Connection rejected")
        active_generation = await manager.active_snapshot(session_id, owner_user_id)
        if active_generation is None:
            refreshed = await asyncio.to_thread(session_snapshot, session_id, owner_user_id)
            if refreshed is None:
                raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Connection rejected")
            snapshot = refreshed
        snapshot["active_generation"] = active_generation
        await websocket.accept()
        await websocket.send_json({"event": "session_snapshot", "data": snapshot})
        sender = asyncio.create_task(_send_chat_events(websocket, subscription))
        expiry = asyncio.create_task(_close_at_expiry(websocket, auth))
        background_tasks = {sender, expiry}
        try:
            await _receive_chat_events(
                websocket,
                settings=settings,
                manager=manager,
                bus=bus,
                session_id=session_id,
                owner_user_id=owner_user_id,
                source_access_token=source_access_token,
            )
        except WebSocketDisconnect:
            pass
        finally:
            for task in background_tasks:
                task.cancel()
            await asyncio.gather(*background_tasks, return_exceptions=True)
