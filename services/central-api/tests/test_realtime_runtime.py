"""Phase 1 coverage for the bounded real-time runtime and stream authentication."""

import asyncio
from datetime import UTC, datetime, timedelta
from threading import Thread

import pytest
from fastapi import HTTPException, WebSocket, WebSocketException
from fastapi.testclient import TestClient
from starlette.requests import Request
from trackflow_auth import ACCESS_COOKIE_NAME  # type: ignore[import-untyped]

from central_api.core.config import Settings
from central_api.domains.realtime.auth import (
    authenticate_http_stream,
    authenticate_websocket_upgrade,
    origin_is_allowed,
)
from central_api.domains.realtime.bus import RealtimeBus, SubscriptionClosed
from central_api.main import create_app


def _request(*, cookie: str | None = None, bearer: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie is not None:
        headers.append((b"cookie", f"{ACCESS_COOKIE_NAME}={cookie}".encode()))
    if bearer is not None:
        headers.append((b"authorization", f"Bearer {bearer}".encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/realtime/rfp/stream",
            "raw_path": b"/realtime/rfp/stream",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("backoffice.forgehub.cloud", 443),
        }
    )


async def _never_receive() -> dict[str, object]:
    return {"type": "websocket.disconnect"}


async def _ignore_send(_message: dict[str, object]) -> None:
    return None


def _websocket(*, origin: str | None, cookie: str | None) -> WebSocket:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if cookie is not None:
        headers.append((b"cookie", f"{ACCESS_COOKIE_NAME}={cookie}".encode()))
    return WebSocket(
        {
            "type": "websocket",
            "scheme": "wss",
            "path": "/realtime/chat/session-id",
            "raw_path": b"/realtime/chat/session-id",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("backoffice.forgehub.cloud", 443),
            "subprotocols": [],
        },
        _never_receive,
        _ignore_send,
    )


def test_bus_fans_out_independent_events_and_ids() -> None:
    async def scenario() -> None:
        bus = RealtimeBus(queue_capacity=4)
        first = bus.subscribe("rfp.tickets.owner")
        second = bus.subscribe("rfp.tickets.owner")
        other_topic = bus.subscribe("rfp.tickets.other")

        first_event = bus.publish("rfp.tickets.owner", "rfp_ticket_created", {"ticket_id": "one"})
        second_event = bus.publish("rfp.tickets.owner", "rfp_ticket_created", {"ticket_id": "two"})

        assert first_event.event_id == 1
        assert second_event.event_id == 2
        assert await asyncio.wait_for(first.receive(), timeout=0.2) == first_event
        assert await asyncio.wait_for(second.receive(), timeout=0.2) == first_event
        assert await asyncio.wait_for(first.receive(), timeout=0.2) == second_event
        assert other_topic.dropped_events == 0
        assert bus.subscriber_count("rfp.tickets.owner") == 2

        first.close()
        second.close()
        other_topic.close()
        assert bus.subscriber_count("rfp.tickets.owner") == 0

    asyncio.run(scenario())


def test_bus_drops_oldest_without_blocking_producer() -> None:
    async def scenario() -> None:
        bus = RealtimeBus(queue_capacity=2, overflow_threshold=3)
        subscription = bus.subscribe("topic")

        for value in range(4):
            bus.publish("topic", "update", {"value": value})

        assert subscription.dropped_events == 2
        assert (await subscription.receive()).data == {"value": 2}
        assert (await subscription.receive()).data == {"value": 3}
        subscription.close()

    asyncio.run(scenario())


def test_bus_evicts_repeatedly_slow_consumer_only() -> None:
    async def scenario() -> None:
        bus = RealtimeBus(queue_capacity=1, overflow_threshold=2)
        slow = bus.subscribe("topic")
        healthy = bus.subscribe("topic")

        bus.publish("topic", "update", {"value": 1})
        assert (await healthy.receive()).data == {"value": 1}
        bus.publish("topic", "update", {"value": 2})
        assert (await healthy.receive()).data == {"value": 2}
        bus.publish("topic", "update", {"value": 3})

        assert slow.closed is True
        assert healthy.closed is False
        assert bus.subscriber_count("topic") == 1
        with pytest.raises(SubscriptionClosed):
            await slow.receive()
        assert (await healthy.receive()).data == {"value": 3}
        healthy.close()

    asyncio.run(scenario())


def test_bus_accepts_publish_from_a_sync_thread() -> None:
    async def scenario() -> None:
        bus = RealtimeBus()
        subscription = bus.subscribe("topic")
        publisher = Thread(target=bus.publish, args=("topic", "update", {"source": "thread"}))
        publisher.start()
        publisher.join(timeout=1)

        assert publisher.is_alive() is False
        assert (await asyncio.wait_for(subscription.receive(), timeout=0.2)).data == {"source": "thread"}
        subscription.close()

    asyncio.run(scenario())


def test_bus_close_wakes_waiters_and_rejects_future_work() -> None:
    async def scenario() -> None:
        bus = RealtimeBus()
        subscription = bus.subscribe("topic")
        waiter = asyncio.create_task(subscription.receive())
        await asyncio.sleep(0)

        bus.close()

        with pytest.raises(SubscriptionClosed):
            await asyncio.wait_for(waiter, timeout=0.2)
        with pytest.raises(RuntimeError, match="closed"):
            bus.publish("topic", "update", {})
        with pytest.raises(RuntimeError, match="closed"):
            bus.subscribe("topic")

    asyncio.run(scenario())


def test_application_shutdown_closes_realtime_bus() -> None:
    app = create_app()
    bus = app.state.realtime_bus

    with TestClient(app):
        bus.publish("topic", "update", {})

    with pytest.raises(RuntimeError, match="closed"):
        bus.publish("topic", "update", {})


def test_http_stream_requires_cookie_and_exposes_token_expiry(
    settings: Settings,
    token_factory: object,
) -> None:
    create_token = token_factory
    assert callable(create_token)
    token = create_token(expires_delta=timedelta(minutes=5))

    authenticated = authenticate_http_stream(_request(cookie=token), settings)

    assert authenticated.principal.user_id == "11111111-1111-4111-8111-111111111111"
    assert authenticated.principal.token_source == "cookie"
    assert authenticated.expires_at > datetime.now(UTC) + timedelta(minutes=4)
    with pytest.raises(HTTPException) as bearer_only:
        authenticate_http_stream(_request(bearer=token), settings)
    assert bearer_only.value.status_code == 401


@pytest.mark.parametrize("origin", [None, "https://evil.example", "https://backoffice.forgehub.cloud/"])
def test_websocket_upgrade_rejects_missing_or_non_exact_origin(
    origin: str | None,
    settings: Settings,
    token_factory: object,
) -> None:
    create_token = token_factory
    assert callable(create_token)
    configured = settings.model_copy(
        update={"central_api_cors_origins": "https://backoffice.forgehub.cloud"}
    )

    assert origin_is_allowed(origin, configured) is False
    with pytest.raises(WebSocketException) as rejected:
        authenticate_websocket_upgrade(_websocket(origin=origin, cookie=create_token()), configured)
    assert rejected.value.code == 1008
    assert rejected.value.reason == "Connection rejected"


def test_websocket_upgrade_accepts_exact_origin_and_cookie(
    settings: Settings,
    token_factory: object,
) -> None:
    create_token = token_factory
    assert callable(create_token)
    origin = "https://backoffice.forgehub.cloud"
    configured = settings.model_copy(update={"central_api_cors_origins": origin})

    authenticated = authenticate_websocket_upgrade(
        _websocket(origin=origin, cookie=create_token()),
        configured,
    )

    assert authenticated.principal.token_source == "cookie"
    assert origin_is_allowed(origin, configured) is True
    with pytest.raises(WebSocketException) as missing_cookie:
        authenticate_websocket_upgrade(_websocket(origin=origin, cookie=None), configured)
    assert missing_cookie.value.reason == "Connection rejected"
