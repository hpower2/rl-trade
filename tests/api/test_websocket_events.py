"""WebSocket event streaming tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.routes.events import router as events_router
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings


def test_event_broadcaster_replays_filtered_events_with_typed_messages() -> None:
    broadcaster = EventBroadcaster(buffer_limit=10)
    broadcaster.publish_event(
        event_type="training_progress",
        entity_type="supervised_training_job",
        entity_id="7",
        payload={"progress_percent": 40},
        occurred_at=datetime(2026, 4, 4, 15, 0, tzinfo=UTC),
    )
    broadcaster.publish_event(
        event_type="signal_event",
        entity_type="paper_trade_signal",
        entity_id="2",
        payload={"status": "accepted"},
        occurred_at=datetime(2026, 4, 4, 15, 1, tzinfo=UTC),
    )

    async def subscribe_and_collect() -> None:
        subscription = broadcaster.subscribe(after=0, topics={"training_progress"})
        try:
            assert len(subscription.replay_messages) == 1
            message = subscription.replay_messages[0]
        finally:
            broadcaster.unsubscribe(subscription)

        assert message.delivery == "replay"
        assert message.event.cursor == 1
        assert message.event.event_id == "evt-1"
        assert message.event.event_type == "training_progress"
        assert message.event.entity_type == "supervised_training_job"
        assert message.event.entity_id == "7"
        assert message.event.payload == {"progress_percent": 40}

    asyncio.run(subscribe_and_collect())


def test_websocket_events_endpoint_streams_live_event() -> None:
    app = build_test_app()
    client = TestClient(app)

    with client.websocket_connect("/ws/events?topics=signal_event") as websocket:
        app.state.event_broadcaster.publish_event(
            event_type="signal_event",
            entity_type="paper_trade_signal",
            entity_id="11",
            payload={"status": "accepted", "symbol_code": "EURUSD"},
        )

        message = websocket.receive_json()

    assert message["delivery"] == "live"
    assert message["event"]["event_type"] == "signal_event"
    assert message["event"]["entity_type"] == "paper_trade_signal"
    assert message["event"]["entity_id"] == "11"
    assert message["event"]["payload"]["symbol_code"] == "EURUSD"


def test_websocket_events_endpoint_replays_buffered_events_with_static_token() -> None:
    app = build_test_app(
        Settings(
        _env_file=None,
        api_auth_mode="static_token",
        api_auth_token="topsecret",
        )
    )
    client = TestClient(app)

    app.state.event_broadcaster.publish_event(
        event_type="training_progress",
        entity_type="rl_training_job",
        entity_id="5",
        payload={"progress_percent": 75},
        occurred_at=datetime(2026, 4, 4, 15, 10, tzinfo=UTC),
    )

    with client.websocket_connect("/ws/events?token=topsecret&topics=training_progress&after=0") as websocket:
        message = websocket.receive_json()

    assert message["delivery"] == "replay"
    assert message["event"]["cursor"] == 1
    assert message["event"]["event_type"] == "training_progress"
    assert message["event"]["entity_id"] == "5"
    assert message["event"]["payload"]["progress_percent"] == 75


def build_test_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(events_router)
    app.state.settings = settings or Settings(_env_file=None)
    app.state.event_broadcaster = EventBroadcaster()
    return app
