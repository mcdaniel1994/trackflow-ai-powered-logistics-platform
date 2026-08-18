"""Bounded in-process fan-out for the single-worker real-time deployment."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from threading import Lock

from .schemas import RealtimeEvent


class SubscriptionClosed(RuntimeError):
    """Signal that a subscription was closed or evicted."""


def rfp_ticket_topic(owner_user_uuid: str) -> str:
    """Return the private topic for one RFP ticket owner."""
    return f"rfp.tickets.{owner_user_uuid}"


def chat_session_topic(session_id: str) -> str:
    """Return the private topic for one owner-authorized chat session."""
    return f"chat.{session_id}"


class RealtimeSubscription:
    """A bounded topic subscription safe to publish to from synchronous threads."""

    def __init__(
        self,
        *,
        topic: str,
        loop: asyncio.AbstractEventLoop,
        capacity: int,
        overflow_threshold: int,
        on_close: Callable[[RealtimeSubscription], None],
    ) -> None:
        self.topic = topic
        self._loop = loop
        self._capacity = capacity
        self._overflow_threshold = overflow_threshold
        self._on_close = on_close
        self._items: deque[RealtimeEvent] = deque(maxlen=capacity)
        self._wake = asyncio.Event()
        self._lock = Lock()
        self._closed = False
        self._wake_scheduled = False
        self._consecutive_overflows = 0
        self._dropped_events = 0

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def dropped_events(self) -> int:
        with self._lock:
            return self._dropped_events

    def _schedule_wake_locked(self) -> None:
        if self._wake_scheduled:
            return
        self._wake_scheduled = True
        try:
            self._loop.call_soon_threadsafe(self._notify)
        except RuntimeError:
            self._wake_scheduled = False

    def _notify(self) -> None:
        with self._lock:
            self._wake_scheduled = False
        self._wake.set()

    def offer(self, event: RealtimeEvent) -> None:
        """Queue an event without waiting; evict this subscriber after repeated overflow."""
        evicted = False
        with self._lock:
            if self._closed:
                return
            if len(self._items) == self._capacity:
                self._dropped_events += 1
                self._consecutive_overflows += 1
            else:
                self._consecutive_overflows = 0
            self._items.append(event)
            if self._consecutive_overflows >= self._overflow_threshold:
                self._closed = True
                self._items.clear()
                evicted = True
            self._schedule_wake_locked()
        if evicted:
            self._on_close(self)

    async def receive(self) -> RealtimeEvent:
        """Wait for the next event, or raise when this subscriber has been closed."""
        while True:
            with self._lock:
                if self._items:
                    return self._items.popleft()
                if self._closed:
                    raise SubscriptionClosed("Realtime subscription is closed")
                self._wake.clear()
            await self._wake.wait()

    def close(self) -> None:
        """Unregister and wake a waiting consumer; safe to call more than once."""
        should_unregister = False
        with self._lock:
            if not self._closed:
                self._closed = True
                self._items.clear()
                should_unregister = True
            self._schedule_wake_locked()
        if should_unregister:
            self._on_close(self)

    async def __aenter__(self) -> RealtimeSubscription:
        return self

    async def __aexit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def __aiter__(self) -> RealtimeSubscription:
        return self

    async def __anext__(self) -> RealtimeEvent:
        try:
            return await self.receive()
        except SubscriptionClosed as exc:
            raise StopAsyncIteration from exc


class RealtimeBus:
    """Thread-safe, process-local topic fan-out with monotonic event identifiers."""

    def __init__(self, *, queue_capacity: int = 64, overflow_threshold: int = 3) -> None:
        if queue_capacity < 1:
            raise ValueError("queue_capacity must be positive")
        if overflow_threshold < 1:
            raise ValueError("overflow_threshold must be positive")
        self._queue_capacity = queue_capacity
        self._overflow_threshold = overflow_threshold
        self._lock = Lock()
        self._next_event_id = 1
        self._subscriptions: dict[str, set[RealtimeSubscription]] = defaultdict(set)
        self._closed = False

    def subscribe(self, topic: str) -> RealtimeSubscription:
        """Register an independent subscriber on the caller's running event loop."""
        normalized_topic = topic.strip()
        if not normalized_topic:
            raise ValueError("topic must not be empty")
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._closed:
                raise RuntimeError("Realtime bus is closed")
            subscription = RealtimeSubscription(
                topic=normalized_topic,
                loop=loop,
                capacity=self._queue_capacity,
                overflow_threshold=self._overflow_threshold,
                on_close=self._remove,
            )
            self._subscriptions[normalized_topic].add(subscription)
        return subscription

    def publish(self, topic: str, event: str, data: Mapping[str, object]) -> RealtimeEvent:
        """Fan out one immutable event without applying consumer backpressure."""
        normalized_topic = topic.strip()
        if not normalized_topic:
            raise ValueError("topic must not be empty")
        normalized_event = event.strip()
        if not normalized_event:
            raise ValueError("event must not be empty")
        with self._lock:
            if self._closed:
                raise RuntimeError("Realtime bus is closed")
            published = RealtimeEvent(
                event_id=self._next_event_id,
                event=normalized_event,
                data=dict(data),
            )
            self._next_event_id += 1
            subscribers = tuple(self._subscriptions.get(normalized_topic, ()))
        for subscription in subscribers:
            subscription.offer(published)
        return published

    def subscriber_count(self, topic: str) -> int:
        with self._lock:
            return len(self._subscriptions.get(topic, ()))

    def _remove(self, subscription: RealtimeSubscription) -> None:
        with self._lock:
            subscribers = self._subscriptions.get(subscription.topic)
            if subscribers is None:
                return
            subscribers.discard(subscription)
            if not subscribers:
                self._subscriptions.pop(subscription.topic, None)

    def close(self) -> None:
        """Close all subscribers and reject future publications."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            subscriptions = tuple(
                subscription
                for topic_subscriptions in self._subscriptions.values()
                for subscription in topic_subscriptions
            )
            self._subscriptions.clear()
        for subscription in subscriptions:
            subscription.close()
