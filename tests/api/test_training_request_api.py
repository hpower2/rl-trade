"""Training request intake API tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import select

from rl_trade_api.api.deps import get_db_session
from rl_trade_api.app import create_app
from rl_trade_data import (
    Base,
    IngestionJob,
    JobStatus,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models.enums import TrainingType


def test_training_request_endpoint_creates_request_and_enqueues_ingestion(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'training_request.sqlite'}"
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
        "/api/v1/training/request",
        json={
            "symbol_code": " eurusd ",
            "training_type": "supervised",
            "timeframes": ["1m", "5m", "15m"],
            "sync_mode": "incremental",
            "lookback_bars": 240,
            "priority": 80,
            "notes": "bootstrap dataset collection",
        },
    )

    assert response.status_code == 200
    assert response.json()["symbol_code"] == "EURUSD"
    assert response.json()["training_type"] == "supervised"
    assert response.json()["ingestion_job_status"] == "pending"

    with session_scope(session_factory) as session:
        training_request = session.scalar(select(TrainingRequest))
        ingestion_job = session.scalar(select(IngestionJob))

    assert training_request is not None
    assert training_request.training_type is TrainingType.SUPERVISED
    assert training_request.requested_timeframes == ["1m", "5m", "15m"]
    assert ingestion_job is not None
    assert ingestion_job.details["trigger"] == "training_request"
    assert ingestion_job.details["training_request_id"] == training_request.id
    assert ingestion_job.details["lookback_bars"] == 240
    assert enqueued["job_id"] == ingestion_job.id
    assert "/api/v1/training/request" in app.openapi()["paths"]
    engine.dispose()


def test_training_request_endpoint_rejects_unknown_symbol(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'training_request_missing.sqlite'}"
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

    response = client.post(
        "/api/v1/training/request",
        json={"symbol_code": "AUDCAD", "training_type": "supervised"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": "http_error",
        "message": "Validated symbol AUDCAD was not found.",
        "details": [],
    }
    engine.dispose()


def test_training_request_endpoint_marks_request_failed_when_enqueue_fails(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'training_request_enqueue_fail.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        session.add(Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5"))

    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def fail_enqueue(*, job_id: int) -> None:
        raise RuntimeError(f"broker unavailable for {job_id}")

    monkeypatch.setattr("rl_trade_api.services.ingestion.run_ingestion_job.delay", fail_enqueue)
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post(
        "/api/v1/training/request",
        json={"symbol_code": "EURUSD", "training_type": "rl"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": "http_error",
        "message": "Unable to enqueue ingestion job for training request.",
        "details": [],
    }

    with session_scope(session_factory) as session:
        training_request = session.scalar(select(TrainingRequest))
        ingestion_job = session.scalar(select(IngestionJob))

    assert training_request is not None
    assert training_request.status is JobStatus.FAILED
    assert ingestion_job is not None
    assert ingestion_job.status is JobStatus.FAILED
    assert ingestion_job.error_message is not None
    engine.dispose()
