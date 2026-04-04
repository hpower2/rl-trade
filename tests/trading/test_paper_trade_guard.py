"""Paper-trading gate tests."""

from __future__ import annotations

from decimal import Decimal

from rl_trade_common.settings import Settings
from rl_trade_data import (
    ApprovedModel,
    Base,
    Symbol,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import ConnectionStatus, ModelType
from rl_trade_trading import MT5ConnectionState, evaluate_paper_trade


def test_evaluate_paper_trade_allows_demo_account_for_approved_symbol(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'paper_guard_allow.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id = seed_approved_symbol(session, code="EURUSD")
        decision = evaluate_paper_trade(
            session,
            settings=Settings(_env_file=None),
            symbol_id=symbol_id,
            confidence=74.0,
            risk_to_reward=2.4,
            connection_state=demo_connection_state(),
            model_type=ModelType.SUPERVISED,
        )

    assert decision.allowed is True
    assert decision.reasons == ()
    assert decision.approved_model is not None
    engine.dispose()


def test_evaluate_paper_trade_blocks_unapproved_symbol(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'paper_guard_symbol.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="GBPUSD", base_currency="GBP", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        decision = evaluate_paper_trade(
            session,
            settings=Settings(_env_file=None),
            symbol_id=symbol.id,
            confidence=74.0,
            risk_to_reward=2.4,
            connection_state=demo_connection_state(),
            model_type=ModelType.SUPERVISED,
        )

    assert decision.allowed is False
    assert decision.reasons == ("symbol_not_approved",)
    assert decision.approved_model is None
    engine.dispose()


def test_evaluate_paper_trade_blocks_live_account_even_for_approved_symbol(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'paper_guard_live.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id = seed_approved_symbol(session, code="USDJPY")
        decision = evaluate_paper_trade(
            session,
            settings=Settings(_env_file=None),
            symbol_id=symbol_id,
            confidence=76.0,
            risk_to_reward=2.8,
            connection_state=MT5ConnectionState(
                status=ConnectionStatus.CONNECTED,
                account_login=456789,
                server_name="Broker-Live",
                account_name="Primary Live",
                account_currency="USD",
                leverage=100,
                is_demo=False,
                trade_allowed=True,
                paper_trading_allowed=False,
                reason="live_account_blocked",
            ),
            model_type=ModelType.SUPERVISED,
        )

    assert decision.allowed is False
    assert decision.reasons == ("live_account_blocked",)
    engine.dispose()


def test_evaluate_paper_trade_collects_metric_and_mt5_block_reasons(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'paper_guard_reasons.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id = seed_approved_symbol(session, code="AUDUSD")
        decision = evaluate_paper_trade(
            session,
            settings=Settings(_env_file=None),
            symbol_id=symbol_id,
            confidence=61.0,
            risk_to_reward=1.6,
            connection_state=MT5ConnectionState(
                status=ConnectionStatus.ERROR,
                account_login=None,
                server_name="Broker-Demo",
                account_name=None,
                account_currency=None,
                leverage=None,
                is_demo=True,
                trade_allowed=None,
                paper_trading_allowed=False,
                reason="initialize_failed",
            ),
            model_type=ModelType.SUPERVISED,
        )

    assert decision.allowed is False
    assert decision.reasons == (
        "mt5_unavailable",
        "confidence_below_threshold",
        "risk_to_reward_below_threshold",
    )
    engine.dispose()


def seed_approved_symbol(session, *, code: str) -> int:
    symbol = Symbol(code=code, base_currency=code[:3], quote_currency=code[3:], provider="mt5")
    session.add(symbol)
    session.flush()
    session.add(
        ApprovedModel(
            symbol_id=symbol.id,
            supervised_model_id=1,
            model_type=ModelType.SUPERVISED.value,
            confidence=Decimal("75.0"),
            risk_to_reward=Decimal("2.5"),
            is_active=True,
        )
    )
    session.flush()
    return symbol.id


def demo_connection_state() -> MT5ConnectionState:
    return MT5ConnectionState(
        status=ConnectionStatus.CONNECTED,
        account_login=123456,
        server_name="Broker-Demo",
        account_name="Practice Demo",
        account_currency="USD",
        leverage=100,
        is_demo=True,
        trade_allowed=True,
        paper_trading_allowed=True,
        reason=None,
    )
