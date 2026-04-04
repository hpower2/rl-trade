"""Pipeline request event emission tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
from rl_trade_data.models import OHLCCandle, PreprocessingJob, Timeframe
from rl_trade_trading import MT5CandleRecord
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.tasks import run_ingestion_job, run_preprocessing_job


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


class WorkerEventGateway:
    def fetch_candles(self, settings, *, symbol_code: str, timeframe: Timeframe, start_time: datetime, count: int):
        return [
            MT5CandleRecord(
                timeframe=timeframe,
                candle_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                open=Decimal("1.1000"),
                high=Decimal("1.1010"),
                low=Decimal("1.0990"),
                close=Decimal("1.1005"),
                volume=Decimal("100"),
                spread=12,
            ),
            MT5CandleRecord(
                timeframe=timeframe,
                candle_time=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
                open=Decimal("1.1005"),
                high=Decimal("1.1020"),
                low=Decimal("1.1000"),
                close=Decimal("1.1015"),
                volume=Decimal("110"),
                spread=11,
            ),
        ]


def test_ingestion_worker_emits_live_ingestion_progress_events(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pipeline_events_ingestion_worker.sqlite'}"
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
                requested_timeframes=["1m"],
                details={"lookback_bars": 50},
            )
        )

    client = build_test_client(session_factory)
    monkeypatch.setattr("rl_trade_worker.tasks.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("rl_trade_worker.task_base.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("rl_trade_worker.tasks.get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr("rl_trade_worker.tasks.MT5Gateway", WorkerEventGateway)
    monkeypatch.setattr("rl_trade_worker.task_base.get_event_publisher", lambda: client.app.state.event_broadcaster)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True, raising=False)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True, raising=False)

    with client.websocket_connect("/ws/events?topics=ingestion_progress") as websocket:
        result = run_ingestion_job.delay(job_id=1)
        assert result.successful()
        messages = _collect_worker_messages(websocket, event_type="ingestion_progress")

    progress_points = [message["event"]["payload"]["progress_percent"] for message in messages]
    statuses = [message["event"]["payload"]["status"] for message in messages]

    assert progress_points[:2] == [0, 5]
    assert progress_points[-1] == 100
    assert statuses[0] == "running"
    assert statuses[-1] == "succeeded"
    assert messages[1]["event"]["payload"]["details"]["phase"] == "fetching"
    assert messages[-1]["event"]["payload"]["candles_written"] == 2
    assert messages[-1]["event"]["payload"]["source"] == "worker_task"
    engine.dispose()


def test_preprocessing_worker_emits_live_preprocessing_progress_events(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'pipeline_events_preprocessing_worker.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        _seed_preprocessing_candles(session, symbol_id=symbol.id)
        session.add(
            PreprocessingJob(
                symbol_id=symbol.id,
                requested_timeframes=["1m", "5m", "15m"],
                details={
                    "primary_timeframe": "1m",
                    "feature_set_name": "baseline_forex",
                    "feature_set_version": "v1",
                    "indicator_window": 3,
                    "label_horizon_bars": 2,
                    "label_min_move_ratio": "0.0005",
                },
            )
        )

    client = build_test_client(session_factory)
    monkeypatch.setattr("rl_trade_worker.tasks.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("rl_trade_worker.task_base.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("rl_trade_worker.task_base.get_event_publisher", lambda: client.app.state.event_broadcaster)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True, raising=False)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True, raising=False)

    with client.websocket_connect("/ws/events?topics=preprocessing_progress") as websocket:
        result = run_preprocessing_job.delay(job_id=1)
        assert result.successful()
        messages = _collect_worker_messages(websocket, event_type="preprocessing_progress")

    progress_points = [message["event"]["payload"]["progress_percent"] for message in messages]
    statuses = [message["event"]["payload"]["status"] for message in messages]

    assert progress_points == [0, 10, 35, 75, 100]
    assert statuses == ["running", "running", "running", "running", "succeeded"]
    assert messages[1]["event"]["payload"]["details"]["feature_set_name"] == "baseline_forex"
    assert messages[4]["event"]["payload"]["dataset_version_id"] == 1
    assert messages[4]["event"]["payload"]["source"] == "worker_task"
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


def _collect_worker_messages(websocket, *, event_type: str) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    for _ in range(8):
        message = websocket.receive_json()
        if message["event"]["event_type"] != event_type:
            continue
        messages.append(message)
        if message["event"]["payload"]["status"] == "succeeded":
            return messages
    raise AssertionError(f"Did not receive terminal succeeded event for {event_type}.")


def _seed_preprocessing_candles(session, *, symbol_id: int) -> None:
    base_time = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    m1_closes = [
        Decimal("1.1000"),
        Decimal("1.1005"),
        Decimal("1.1010"),
        Decimal("1.1015"),
        Decimal("1.1020"),
        Decimal("1.1025"),
        Decimal("1.1030"),
        Decimal("1.1035"),
    ]

    for index, close in enumerate(m1_closes):
        open_price = close - Decimal("0.0002")
        session.add(
            OHLCCandle(
                symbol_id=symbol_id,
                timeframe=Timeframe.M1,
                candle_time=base_time + timedelta(minutes=index),
                open=open_price,
                high=close + Decimal("0.0003"),
                low=open_price - Decimal("0.0003"),
                close=close,
                volume=Decimal("100") + Decimal(index),
                provider="mt5",
                source="historical",
            )
        )
        session.flush()

    for minute_offset, open_price, close in [
        (0, Decimal("1.1000"), Decimal("1.1015")),
        (5, Decimal("1.1015"), Decimal("1.1035")),
    ]:
        session.add(
            OHLCCandle(
                symbol_id=symbol_id,
                timeframe=Timeframe.M5,
                candle_time=base_time + timedelta(minutes=minute_offset),
                open=open_price,
                high=close + Decimal("0.0004"),
                low=open_price - Decimal("0.0004"),
                close=close,
                volume=Decimal("250"),
                provider="mt5",
                source="historical",
            )
        )
        session.flush()

    session.add(
        OHLCCandle(
            symbol_id=symbol_id,
            timeframe=Timeframe.M15,
            candle_time=base_time,
            open=Decimal("1.0995"),
            high=Decimal("1.1040"),
            low=Decimal("1.0990"),
            close=Decimal("1.1035"),
            volume=Decimal("500"),
            provider="mt5",
            source="historical",
        )
    )
    session.flush()
