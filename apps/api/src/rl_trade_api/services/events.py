"""In-process WebSocket event broadcasting primitives."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from typing import Any

from rl_trade_api.schemas.events import EVENT_TYPES, EventEnvelope, WebSocketEventMessage


@dataclass(slots=True)
class EventSubscription:
    subscription_id: int
    queue: asyncio.Queue[WebSocketEventMessage]
    replay_messages: list[WebSocketEventMessage]


@dataclass(slots=True)
class _Subscriber:
    topics: frozenset[str] | None
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[WebSocketEventMessage]


class EventBroadcaster:
    def __init__(self, *, buffer_limit: int = 200) -> None:
        self._buffer: deque[EventEnvelope] = deque(maxlen=buffer_limit)
        self._sequence = count(start=1)
        self._subscriptions: dict[int, _Subscriber] = {}
        self._subscription_ids = count(start=1)

    def publish_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> EventEnvelope:
        normalized_event_type = _normalize_event_type(event_type)
        cursor = next(self._sequence)
        event = EventEnvelope(
            cursor=cursor,
            event_id=f"evt-{cursor}",
            event_type=normalized_event_type,
            occurred_at=(occurred_at or datetime.now(UTC)).astimezone(UTC),
            entity_type=entity_type,
            entity_id=entity_id,
            payload=dict(payload or {}),
        )
        self._buffer.append(event)

        message = WebSocketEventMessage(delivery="live", event=event)
        for subscription in self._subscriptions.values():
            if not _matches_topics(event=event, topics=subscription.topics):
                continue
            subscription.loop.call_soon_threadsafe(subscription.queue.put_nowait, message)

        return event

    def subscribe(self, *, after: int | None = None, topics: set[str] | None = None) -> EventSubscription:
        normalized_topics = frozenset(_normalize_event_type(topic) for topic in topics) if topics else None
        subscription_id = next(self._subscription_ids)
        queue: asyncio.Queue[WebSocketEventMessage] = asyncio.Queue()
        self._subscriptions[subscription_id] = _Subscriber(
            topics=normalized_topics,
            loop=asyncio.get_running_loop(),
            queue=queue,
        )
        replay_messages = [
            WebSocketEventMessage(delivery="replay", event=event)
            for event in self._buffer
            if _matches_after(event=event, after=after) and _matches_topics(event=event, topics=normalized_topics)
        ]
        return EventSubscription(
            subscription_id=subscription_id,
            queue=queue,
            replay_messages=replay_messages,
        )

    def unsubscribe(self, subscription: EventSubscription) -> None:
        self._subscriptions.pop(subscription.subscription_id, None)


def _normalize_event_type(event_type: str) -> str:
    normalized = str(event_type).strip().lower()
    if normalized not in EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}.")
    return normalized


def _matches_after(*, event: EventEnvelope, after: int | None) -> bool:
    if after is None:
        return True
    return event.cursor > after


def _matches_topics(*, event: EventEnvelope, topics: frozenset[str] | None) -> bool:
    if not topics:
        return True
    return event.event_type in topics
