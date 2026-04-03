"""Preprocessing API endpoint tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from rl_trade_api.api.deps import get_db_session
from rl_trade_api.app import create_app
from rl_trade_data import (
    Base,
    DatasetVersion,
    OHLCCandle,
    PreprocessingJob,
    Symbol,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import Timeframe
from rl_trade_worker.celery_app import celery_app


def test_preprocessing_request_endpoint_creates_job_and_enqueues_worker(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'preprocessing_request.sqlite'}"
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
        "rl_trade_api.services.preprocessing.run_preprocessing_job.delay",
        lambda *, job_id: enqueued.setdefault("job_id", job_id),
    )
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

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

    assert response.status_code == 200
    assert response.json()["symbol_code"] == "EURUSD"
    assert response.json()["requested_timeframes"] == ["1m", "5m", "15m"]

    with session_scope(session_factory) as session:
        job = session.scalar(select(PreprocessingJob))

    assert job is not None
    assert job.details["primary_timeframe"] == "1m"
    assert job.details["feature_set_name"] == "baseline_forex"
    assert enqueued["job_id"] == job.id
    assert "/api/v1/preprocessing/request" in app.openapi()["paths"]
    engine.dispose()


def test_preprocessing_request_endpoint_drives_end_to_end_dataset_build(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'preprocessing_end_to_end.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        seed_market_candles(session, symbol_id=symbol.id)

    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("rl_trade_worker.tasks.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("rl_trade_worker.task_base.get_session_factory", lambda: session_factory)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True, raising=False)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False, raising=False)
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post(
        "/api/v1/preprocessing/request",
        json={
            "symbol_code": "EURUSD",
            "timeframes": ["1m", "5m", "15m"],
            "primary_timeframe": "1m",
            "feature_set_name": "baseline_forex",
            "feature_set_version": "v1",
            "indicator_window": 3,
            "label_horizon_bars": 2,
            "label_min_move_ratio": "0.0005",
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    job_response = client.get(f"/api/v1/jobs/preprocessing/{job_id}")

    assert job_response.status_code == 200
    assert job_response.json()["status"] == "succeeded"
    assert job_response.json()["queue_name"] == "preprocessing"
    assert job_response.json()["details"]["dataset_version_tag"]

    with session_scope(session_factory) as session:
        dataset_version = session.scalar(select(DatasetVersion))
        preprocessing_job = session.get(PreprocessingJob, job_id)

    assert dataset_version is not None
    assert preprocessing_job is not None
    assert preprocessing_job.dataset_version_id == dataset_version.id
    assert preprocessing_job.feature_set_id is not None
    engine.dispose()


def seed_market_candles(session, *, symbol_id: int) -> None:
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
