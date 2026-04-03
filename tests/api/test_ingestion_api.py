"""Ingestion API endpoint tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from rl_trade_api.api.deps import get_db_session
from rl_trade_api.app import create_app
from rl_trade_data import Base, IngestionJob, JobStatus, Symbol, build_engine, build_session_factory, session_scope


def test_ingestion_request_endpoint_creates_job_and_enqueues_worker(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'ingestion_request.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        session.add(Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5"))

    app = create_app()
    enqueued: dict[str, int] = {}

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        "rl_trade_api.services.ingestion.run_ingestion_job.delay",
        lambda *, job_id: enqueued.setdefault("job_id", job_id),
    )
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post(
        "/api/v1/ingestion/request",
        json={"symbol_code": "eurusd", "timeframes": ["1m", "5m"], "sync_mode": "incremental", "lookback_bars": 120},
    )

    assert response.status_code == 200
    assert response.json()["symbol_code"] == "EURUSD"
    assert response.json()["requested_timeframes"] == ["1m", "5m"]
    assert response.json()["sync_mode"] == "incremental"

    with session_scope(session_factory) as session:
        job = session.scalar(select(IngestionJob).where(IngestionJob.symbol_id == 1))

    assert job is not None
    assert job.requested_timeframes == ["1m", "5m"]
    assert job.details["lookback_bars"] == 120
    assert enqueued["job_id"] == job.id
    assert "/api/v1/ingestion/request" in app.openapi()["paths"]
    engine.dispose()


def test_ingestion_request_endpoint_rejects_unknown_symbol(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'ingestion_request_missing.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post("/api/v1/ingestion/request", json={"symbol_code": "AUDCAD"})

    assert response.status_code == 404
    assert response.json() == {
        "error": "http_error",
        "message": "Validated symbol AUDCAD was not found.",
        "details": [],
    }
    engine.dispose()


def test_ingestion_retry_endpoint_requeues_failed_job(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'ingestion_retry.sqlite'}"
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

    app = create_app()
    enqueued: dict[str, int] = {}

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        "rl_trade_api.services.ingestion.run_ingestion_job.delay",
        lambda *, job_id: enqueued.setdefault("job_id", job_id),
    )
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post("/api/v1/ingestion/1/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["progress_percent"] == 0
    assert response.json()["candles_requested"] is None
    assert response.json()["candles_written"] == 0
    assert response.json()["last_successful_candle_time"] is None

    with session_scope(session_factory) as session:
        job = session.get(IngestionJob, 1)

    assert job is not None
    assert job.status is JobStatus.PENDING
    assert job.progress_percent == 0
    assert job.candles_requested is None
    assert job.candles_written == 0
    assert job.finished_at is None
    assert job.error_message is None
    assert job.details["manual_retry_count"] == 1
    assert job.details["last_manual_retry_by"] == "operator"
    assert enqueued["job_id"] == job.id
    assert "/api/v1/ingestion/{job_id}/retry" in app.openapi()["paths"]
    engine.dispose()


def test_ingestion_retry_endpoint_rejects_non_failed_job(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'ingestion_retry_conflict.sqlite'}"
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
                status=JobStatus.PENDING,
                sync_mode="incremental",
                requested_timeframes=["1m"],
                source_provider="mt5",
            )
        )

    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post("/api/v1/ingestion/1/retry")

    assert response.status_code == 409
    assert response.json() == {
        "error": "http_error",
        "message": "Ingestion job 1 cannot be retried from status pending.",
        "details": [],
    }
    engine.dispose()
