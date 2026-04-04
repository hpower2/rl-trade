"""WebSocket routes for live event streaming."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from rl_trade_api.schemas.events import EVENT_TYPES
from rl_trade_api.services import auth as auth_service
from rl_trade_api.services.events import EventBroadcaster

router = APIRouter()


@router.websocket("/ws/events")
async def stream_events(websocket: WebSocket) -> None:
    settings = websocket.app.state.settings
    token = websocket.query_params.get("token")
    if auth_service.resolve_token_principal(settings=settings, token=token) is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required.")
        return

    try:
        after = _parse_after(websocket.query_params.get("after"))
        topics = _parse_topics(websocket.query_params.get("topics"))
    except ValueError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc))
        return

    broadcaster: EventBroadcaster = websocket.app.state.event_broadcaster
    await websocket.accept()
    subscription = broadcaster.subscribe(after=after, topics=topics)

    try:
        for message in subscription.replay_messages:
            await websocket.send_json(message.model_dump(mode="json"))
        while True:
            message = await subscription.queue.get()
            await websocket.send_json(message.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    finally:
        broadcaster.unsubscribe(subscription)


def _parse_after(raw_value: str | None) -> int | None:
    if raw_value is None or not raw_value.strip():
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("Invalid after cursor.") from exc
    if value < 0:
        raise ValueError("Invalid after cursor.")
    return value


def _parse_topics(raw_value: str | None) -> set[str] | None:
    if raw_value is None or not raw_value.strip():
        return None
    topics = {part.strip().lower() for part in raw_value.split(",") if part.strip()}
    if not topics:
        return None
    invalid_topics = sorted(topic for topic in topics if topic not in EVENT_TYPES)
    if invalid_topics:
        raise ValueError(f"Unsupported event topics: {', '.join(invalid_topics)}.")
    return topics
