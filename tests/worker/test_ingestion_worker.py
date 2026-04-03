"""Worker-side ingestion execution tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from rl_trade_common.settings import Settings
from rl_trade_data import Base, IngestionJob, OHLCCandle, Symbol, build_engine, build_session_factory, session_scope
from rl_trade_data.models import Timeframe
from rl_trade_worker.services.ingestion import perform_ingestion_job, resolve_ingestion_start_time
from rl_trade_trading import MT5CandleRecord


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Timeframe, datetime, int]] = []

    def fetch_candles(self, settings, *, symbol_code: str, timeframe: Timeframe, start_time: datetime, count: int):
        self.calls.append((symbol_code, timeframe, start_time, count))
        if timeframe == Timeframe.M1:
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
        return [
            MT5CandleRecord(
                timeframe=timeframe,
                candle_time=datetime(2026, 1, 1, 0, 5 if timeframe == Timeframe.M5 else 0, tzinfo=UTC),
                open=Decimal("1.1000"),
                high=Decimal("1.1025"),
                low=Decimal("1.0995"),
                close=Decimal("1.1010"),
                volume=Decimal("200"),
                spread=10,
            )
        ]


class FlakyGateway(FakeGateway):
    def __init__(self) -> None:
        super().__init__()
        self.fail_m5_once = True

    def fetch_candles(self, settings, *, symbol_code: str, timeframe: Timeframe, start_time: datetime, count: int):
        if timeframe == Timeframe.M5 and self.fail_m5_once:
            self.fail_m5_once = False
            raise RuntimeError("temporary mt5 failure")
        return super().fetch_candles(
            settings,
            symbol_code=symbol_code,
            timeframe=timeframe,
            start_time=start_time,
            count=count,
        )


def test_perform_ingestion_job_persists_candles_and_updates_job(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'worker_ingestion.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    gateway = FakeGateway()
    progress_updates: list[tuple[int, dict[str, object] | None]] = []

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        session.add(
            IngestionJob(
                symbol_id=symbol.id,
                requested_timeframes=["1m", "5m", "15m"],
                details={"lookback_bars": 50},
            )
        )

    with session_scope(session_factory) as session:
        job = session.scalar(select(IngestionJob))
        result = perform_ingestion_job(
            session=session,
            gateway=gateway,
            settings=Settings(_env_file=None),
            job_id=job.id,
            progress_callback=lambda progress, details=None: progress_updates.append((progress, details)),
        )

    with session_scope(session_factory) as session:
        stored_job = session.get(IngestionJob, job.id)
        stored_candles = session.execute(select(OHLCCandle).order_by(OHLCCandle.timeframe, OHLCCandle.candle_time)).scalars().all()

    assert result["candles_requested"] == 4
    assert result["candles_written"] == 4
    assert stored_job is not None
    assert stored_job.candles_requested == 4
    assert stored_job.candles_written == 4
    normalized_last_successful = stored_job.last_successful_candle_time
    if normalized_last_successful is not None and normalized_last_successful.tzinfo is None:
        normalized_last_successful = normalized_last_successful.replace(tzinfo=UTC)
    assert normalized_last_successful == datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    assert len(stored_candles) == 4
    assert progress_updates
    engine.dispose()


def test_incremental_ingestion_start_time_advances_past_last_candle(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'worker_incremental.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="GBPUSD", base_currency="GBP", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        session.add(
            OHLCCandle(
                symbol_id=symbol.id,
                timeframe=Timeframe.M5,
                candle_time=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
                open=Decimal("1.2500"),
                high=Decimal("1.2510"),
                low=Decimal("1.2490"),
                close=Decimal("1.2505"),
                volume=Decimal("50"),
            )
        )
        session.flush()
        symbol_id = symbol.id

    with session_scope(session_factory) as session:
        start_time = resolve_ingestion_start_time(
            session=session,
            symbol_id=symbol_id,
            timeframe=Timeframe.M5,
            sync_mode="incremental",
            lookback_bars=100,
        )

    assert start_time == datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    engine.dispose()


def test_perform_ingestion_job_resumes_remaining_timeframes_after_failure(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'worker_resume.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    gateway = FlakyGateway()

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        session.add(
            IngestionJob(
                symbol_id=symbol.id,
                requested_timeframes=["1m", "5m", "15m"],
                details={"lookback_bars": 50},
            )
        )

    with session_scope(session_factory) as session:
        job = session.scalar(select(IngestionJob))
        try:
            perform_ingestion_job(
                session=session,
                gateway=gateway,
                settings=Settings(_env_file=None),
                job_id=job.id,
            )
        except RuntimeError as exc:
            assert str(exc) == "temporary mt5 failure"
        else:
            raise AssertionError("Expected the first ingestion attempt to fail.")

    with session_scope(session_factory) as session:
        failed_job = session.get(IngestionJob, 1)
        stored_candles = session.execute(select(OHLCCandle).order_by(OHLCCandle.timeframe, OHLCCandle.candle_time)).scalars().all()

    assert failed_job is not None
    assert failed_job.details["timeframe_progress"]["1m"]["status"] == "succeeded"
    assert failed_job.details["timeframe_progress"]["5m"]["status"] == "failed"
    assert failed_job.details["resume_pending_timeframes"] == ["5m", "15m"]
    assert len(stored_candles) == 2

    gateway.calls.clear()

    with session_scope(session_factory) as session:
        result = perform_ingestion_job(
            session=session,
            gateway=gateway,
            settings=Settings(_env_file=None),
            job_id=1,
        )

    with session_scope(session_factory) as session:
        resumed_job = session.get(IngestionJob, 1)
        resumed_candles = session.execute(select(OHLCCandle).order_by(OHLCCandle.timeframe, OHLCCandle.candle_time)).scalars().all()

    assert [call[1] for call in gateway.calls] == [Timeframe.M5, Timeframe.M15]
    assert result["candles_requested"] == 2
    assert result["candles_written"] == 2
    assert resumed_job is not None
    assert resumed_job.details["completed_timeframes"] == ["1m", "5m", "15m"]
    assert resumed_job.details["resume_pending_timeframes"] == []
    assert len(resumed_candles) == 4
    engine.dispose()


def test_perform_ingestion_job_deduplicates_existing_candles(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'worker_dedup.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    gateway = FakeGateway()

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        session.add(
            IngestionJob(
                symbol_id=symbol.id,
                requested_timeframes=["1m"],
                sync_mode="backfill",
                details={"lookback_bars": 50},
            )
        )
        session.add(
            IngestionJob(
                symbol_id=symbol.id,
                requested_timeframes=["1m"],
                sync_mode="backfill",
                details={"lookback_bars": 50},
            )
        )

    with session_scope(session_factory) as session:
        first_job = session.get(IngestionJob, 1)
        first_result = perform_ingestion_job(
            session=session,
            gateway=gateway,
            settings=Settings(_env_file=None),
            job_id=first_job.id,
        )

    with session_scope(session_factory) as session:
        second_job = session.get(IngestionJob, 2)
        second_result = perform_ingestion_job(
            session=session,
            gateway=gateway,
            settings=Settings(_env_file=None),
            job_id=second_job.id,
        )

    with session_scope(session_factory) as session:
        stored_candles = session.execute(select(OHLCCandle).order_by(OHLCCandle.candle_time)).scalars().all()

    assert first_result["candles_written"] == 2
    assert second_result["candles_requested"] == 2
    assert second_result["candles_written"] == 0
    assert len(stored_candles) == 2
    engine.dispose()
