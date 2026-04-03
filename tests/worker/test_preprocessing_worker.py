"""Worker-side preprocessing execution tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from rl_trade_data import (
    Base,
    DatasetVersion,
    FeatureSet,
    OHLCCandle,
    PreprocessingJob,
    Symbol,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import Timeframe
from rl_trade_worker.services.preprocessing import perform_preprocessing_job


def test_perform_preprocessing_job_builds_dataset_version(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'worker_preprocessing.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    progress_updates: list[tuple[int, dict[str, object] | None]] = []

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        seed_market_candles(session, symbol_id=symbol.id)
        session.add(
            PreprocessingJob(
                symbol_id=symbol.id,
                requested_timeframes=["1m", "5m", "15m"],
                details={
                    "feature_set_name": "baseline_forex",
                    "feature_set_version": "v1",
                    "indicator_window": 3,
                    "label_horizon_bars": 2,
                    "label_min_move_ratio": "0.0005",
                },
            )
        )

    with session_scope(session_factory) as session:
        job = session.scalar(select(PreprocessingJob))
        result = perform_preprocessing_job(
            session=session,
            job_id=job.id,
            progress_callback=lambda progress, details=None: progress_updates.append((progress, details)),
        )

    with session_scope(session_factory) as session:
        stored_job = session.get(PreprocessingJob, 1)
        stored_feature_set = session.scalar(select(FeatureSet))
        stored_dataset = session.scalar(select(DatasetVersion))

    assert result["feature_set_id"] == stored_feature_set.id
    assert result["dataset_version_id"] == stored_dataset.id
    assert result["row_count"] == stored_dataset.row_count
    assert stored_job is not None
    assert stored_job.feature_set_id == stored_feature_set.id
    assert stored_job.dataset_version_id == stored_dataset.id
    assert stored_job.details["feature_set_name"] == "baseline_forex"
    assert stored_job.details["dataset_version_tag"] == stored_dataset.version_tag
    assert stored_feature_set.feature_columns
    assert "m5_trend" in stored_feature_set.feature_columns
    assert "pattern_doji" in stored_feature_set.feature_columns
    assert stored_dataset.row_count is not None and stored_dataset.row_count > 0
    assert stored_dataset.label_name == "direction"
    assert stored_dataset.details["feature_columns"]
    assert progress_updates
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

    m5_points = [
        (0, Decimal("1.1000"), Decimal("1.1015")),
        (5, Decimal("1.1015"), Decimal("1.1035")),
    ]
    for minute_offset, open_price, close in m5_points:
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
