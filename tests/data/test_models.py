"""ORM smoke tests for the application schema."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from rl_trade_data import Base, build_engine, build_session_factory, session_scope
from rl_trade_data.models import OHLCCandle, Symbol, Timeframe


def test_symbol_and_candle_can_be_created_and_queried(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'models.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD")
        session.add(symbol)
        session.flush()
        session.add(
            OHLCCandle(
                symbol_id=symbol.id,
                timeframe=Timeframe.M1,
                candle_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
                open=Decimal("1.10000"),
                high=Decimal("1.10100"),
                low=Decimal("1.09950"),
                close=Decimal("1.10050"),
                volume=Decimal("100"),
            )
        )

    with session_scope(session_factory) as session:
        stored_symbol = session.scalar(select(Symbol).where(Symbol.code == "EURUSD"))
        stored_candle = session.scalar(select(OHLCCandle).where(OHLCCandle.symbol_id == stored_symbol.id))

    assert stored_symbol is not None
    assert stored_candle is not None
    assert stored_candle.timeframe == Timeframe.M1
    assert stored_candle.close == Decimal("1.10050000")
    engine.dispose()


def test_ohlc_candle_dedup_constraint_rejects_duplicates(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'ohlc_dedup.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    candle_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="GBPUSD", base_currency="GBP", quote_currency="USD")
        session.add(symbol)
        session.flush()
        session.add(
            OHLCCandle(
                symbol_id=symbol.id,
                timeframe=Timeframe.M5,
                candle_time=candle_time,
                open=Decimal("1.25000"),
                high=Decimal("1.25100"),
                low=Decimal("1.24900"),
                close=Decimal("1.25050"),
                volume=Decimal("50"),
            )
        )

    with pytest.raises(IntegrityError):
        with session_scope(session_factory) as session:
            existing_symbol = session.scalar(select(Symbol).where(Symbol.code == "GBPUSD"))
            session.add(
                OHLCCandle(
                    symbol_id=existing_symbol.id,
                    timeframe=Timeframe.M5,
                    candle_time=candle_time,
                    open=Decimal("1.25010"),
                    high=Decimal("1.25110"),
                    low=Decimal("1.24910"),
                    close=Decimal("1.25060"),
                    volume=Decimal("51"),
                )
            )

    engine.dispose()
