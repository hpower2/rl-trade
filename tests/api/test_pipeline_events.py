"""Pipeline request event emission tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_db_session, require_authenticated_principal
from rl_trade_api.api.routes.events import router as events_router
from rl_trade_api.api.v1.routes.ingestion import router as ingestion_router
from rl_trade_api.api.v1.routes.preprocessing import router as preprocessing_router
from rl_trade_api.services import ingestion as ingestion_service
from rl_trade_api.services import preprocessing as preprocessing_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings
from rl_trade_data import Base, IngestionJob, JobStatus, Symbol, build_engine, build_session_factory, session_scope


def test_ingestion_request_emits_live_ingestion_progress_event(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pipeline_events_ingestion_request.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        session.add(Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5"))

    monkeypatch.setattr(ingestion_service, "_enqueue_ingestion_job", lambda *, job_id: None)
    client = build_test_client(session_factory)

    with client.websocket_connect("/ws/events?topics=ingestion_progress") as websocket:
        response = client.post(
            "/api/v1/ingestion/request",
            json={"symbol_code": "eurusd", "timeframes": ["1m", "5m"], "sync_mode": "incremental", "lookback_bars": 120},
        )
        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["delivery"] == "live"
    assert message["event"]["event_type"] == "ingestion_progress"
    assert message["event"]["entity_type"] == "ingestion_job"
    assert message["event"]["entity_id"] == "1"
    assert message["event"]["payload"] == {
        "job_id": 1,
        "symbol_id": 1,
        "symbol_code": "EURUSD",
        "status": "pending",
        "progress_percent": 0,
        "sync_mode": "incremental",
        "requested_timeframes": ["1m", "5m"],
        "source_provider": "mt5",
        "source": "api_request",
    }
    engine.dispose()


def test_ingestion_retry_emits_live_ingestion_progress_event(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pipeline_events_ingestion_retry.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        session.add(
            IngestionJob(
                symbol_id=symbol.id,
                status=JobStatus.FAILED,
                sync_mode="incremental",
                requested_by="operator",
                requested_timeframes=["1m", "5m"],
                source_provider="mt5",
                progress_percent=65,
                candles_requested=240,
                candles_written=180,
                last_successful_candle_time=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
                started_at=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                finished_at=datetime(2026, 1, 1, 0, 6, tzinfo=UTC),
                error_message="mt5 timeout",
                details={"lookback_bars": 120},
            )
        )

    monkeypatch.setattr(ingestion_service, "_enqueue_ingestion_job", lambda *, job_id: None)
    client = build_test_client(session_factory)

    with client.websocket_connect("/ws/events?topics=ingestion_progress") as websocket:
        response = client.post("/api/v1/ingestion/1/retry")
        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["delivery"] == "live"
    assert message["event"]["event_type"] == "ingestion_progress"
    assert message["event"]["entity_id"] == "1"
    assert message["event"]["payload"]["status"] == "pending"
    assert message["event"]["payload"]["progress_percent"] == 0
    assert message["event"]["payload"]["source"] == "manual_retry"
    engine.dispose()


def test_preprocessing_request_emits_live_preprocessing_progress_event(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pipeline_events_preprocessing_request.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        session.add(Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5"))

    monkeypatch.setattr(preprocessing_service, "_enqueue_preprocessing_job", lambda *, job_id: None)
    client = build_test_client(session_factory)

    with client.websocket_connect("/ws/events?topics=preprocessing_progress") as websocket:
        response = client.post(
            "/api/v1/preprocessing/request",
            json={
                "symbol_code": "eurusd",
                "timeframes": ["1m", "5m", "15m"],
                "primary_timeframe": "1m",
                "feature_set_name": "baseline_forex",
                "feature_set_version": "v1",
            },
        )
        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["delivery"] == "live"
    assert message["event"]["event_type"] == "preprocessing_progress"
    assert message["event"]["entity_type"] == "preprocessing_job"
    assert message["event"]["entity_id"] == "1"
    assert message["event"]["payload"] == {
        "job_id": 1,
        "symbol_id": 1,
        "symbol_code": "EURUSD",
        "status": "pending",
        "progress_percent": 0,
        "requested_timeframes": ["1m", "5m", "15m"],
        "primary_timeframe": "1m",
        "feature_set_name": "baseline_forex",
        "feature_set_version": "v1",
        "source": "api_request",
    }
    engine.dispose()


def build_test_client(session_factory) -> TestClient:
    app = FastAPI()
    app.include_router(events_router)
    app.include_router(ingestion_router, prefix="/api/v1")
    app.include_router(preprocessing_router, prefix="/api/v1")
    app.state.settings = Settings(_env_file=None)
    app.state.event_broadcaster = EventBroadcaster()
    app.dependency_overrides[require_authenticated_principal] = lambda: AuthPrincipal(
        subject="operator",
        roles=("operator",),
        auth_mode="disabled",
    )

    def override_db_session() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)
