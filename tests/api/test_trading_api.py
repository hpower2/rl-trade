"""Paper-trading signal API tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_api_settings, get_db_session, get_mt5_gateway, require_authenticated_principal
from rl_trade_api.api.v1.routes.trading import router as trading_router
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings
from rl_trade_data import (
    ApprovedModel,
    AuditLog,
    Base,
    EquitySnapshot,
    MT5Account,
    PaperTradeOrder,
    PaperTradePosition,
    PaperTradeSignal,
    TradeExecution,
    Symbol,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import AuditOutcome, ConnectionStatus, ModelType, OrderStatus, PositionStatus, SignalStatus, Timeframe, TradeSide
from rl_trade_trading import MT5ConnectionState, MT5HistoricalOrderRecord, MT5OrderResult, MT5PositionRecord


class FakeMT5Gateway:
    def __init__(
        self,
        connection_state: MT5ConnectionState,
        *,
        order_result: MT5OrderResult | None = None,
        order_history: list[MT5HistoricalOrderRecord] | None = None,
        open_positions: list[MT5PositionRecord] | None = None,
    ) -> None:
        self._connection_state = connection_state
        self._order_result = order_result or MT5OrderResult(
            accepted=True,
            filled=True,
            broker_order_id="1001",
            execution_price=Decimal("1.1010"),
            execution_quantity=Decimal("0.25"),
            execution_time=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
            raw_result={"retcode": 10009},
        )
        self._order_history = order_history or []
        self._open_positions = open_positions or []

    def get_connection_state(self, settings: Settings) -> MT5ConnectionState:
        return self._connection_state

    def submit_paper_order(self, settings: Settings, **kwargs) -> MT5OrderResult:
        return self._order_result

    def list_order_history(self, settings: Settings, *, start_time: datetime, end_time: datetime | None = None) -> list[MT5HistoricalOrderRecord]:
        return list(self._order_history)

    def list_open_positions(self, settings: Settings) -> list[MT5PositionRecord]:
        return list(self._open_positions)


def test_create_signal_persists_accepted_signal_and_audit_log(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_signal_accept.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        seed_approved_symbol(session, code="EURUSD")

    client = build_test_client(session_factory, connection_state=demo_connection_state())

    response = client.post(
        "/api/v1/trading/signals",
        json={
            "symbol_code": "EURUSD",
            "timeframe": "1m",
            "side": "long",
            "confidence": 74.0,
            "entry_price": 1.1000,
            "stop_loss": 1.0950,
            "take_profit": 1.1100,
            "model_type": "supervised",
            "rationale": {"source": "integration_test"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["symbol_code"] == "EURUSD"
    assert body["risk_to_reward"] == 2.0

    with session_scope(session_factory) as session:
        signals = session.query(PaperTradeSignal).all()
        audit_logs = session.query(AuditLog).all()

    assert len(signals) == 1
    assert signals[0].status is SignalStatus.ACCEPTED
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.SUCCESS
    engine.dispose()


def test_start_trading_persists_runtime_state_and_status_counts(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_runtime_start.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, approved_model_id = seed_approved_symbol(session, code="EURUSD")
        session.add(
            PaperTradeSignal(
                approved_model_id=approved_model_id,
                symbol_id=symbol_id,
                timeframe=Timeframe.M1,
                side=TradeSide.LONG,
                status=SignalStatus.ACCEPTED,
                signal_time=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
                confidence=Decimal("74.0"),
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
            )
        )

    client = build_test_client(session_factory, connection_state=demo_connection_state())
    start_response = client.post("/api/v1/trading/start")

    assert start_response.status_code == 200
    start_body = start_response.json()
    assert start_body["enabled"] is True
    assert start_body["approved_symbol_count"] == 1
    assert start_body["accepted_signal_count"] == 1
    assert start_body["connection_status"] == "connected"

    status_response = client.get("/api/v1/trading/status")
    assert status_response.status_code == 200
    assert status_response.json()["enabled"] is True
    assert status_response.json()["last_started_by"] == "test-operator"

    with session_scope(session_factory) as session:
        accounts = session.query(MT5Account).all()
        audit_logs = session.query(AuditLog).filter(AuditLog.action == "paper_trading_runtime").all()

    assert len(accounts) == 1
    assert accounts[0].is_demo is True
    assert accounts[0].details["paper_trading_enabled"] is True
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.SUCCESS
    engine.dispose()


def test_start_trading_blocks_live_account(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_runtime_live.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    client = build_test_client(
        session_factory,
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
    )
    response = client.post("/api/v1/trading/start")

    assert response.status_code == 409
    assert "live_account_blocked" in response.json()["detail"]

    with session_scope(session_factory) as session:
        accounts = session.query(MT5Account).all()
        audit_logs = session.query(AuditLog).filter(AuditLog.action == "paper_trading_runtime").all()

    assert accounts == []
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.BLOCKED
    engine.dispose()


def test_stop_trading_disables_runtime_state(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_runtime_stop.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        account = MT5Account(
            account_login=123456,
            server_name="Broker-Demo",
            account_name="Practice Demo",
            account_currency="USD",
            leverage=100,
            is_demo=True,
            connection_status=ConnectionStatus.CONNECTED,
            is_trade_allowed=True,
            details={
                "paper_trading_enabled": True,
                "last_started_at": "2026-04-04T12:00:00+00:00",
                "last_started_by": "test-operator",
            },
        )
        session.add(account)

    client = build_test_client(session_factory, connection_state=demo_connection_state())
    response = client.post("/api/v1/trading/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["last_stopped_by"] == "test-operator"

    with session_scope(session_factory) as session:
        account = session.query(MT5Account).one()

    assert account.details["paper_trading_enabled"] is False
    assert account.details["last_stopped_by"] == "test-operator"
    engine.dispose()


def test_create_signal_blocks_unapproved_symbol_and_records_audit_log(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_signal_block.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        session.add(Symbol(code="GBPUSD", base_currency="GBP", quote_currency="USD", provider="mt5"))

    client = build_test_client(session_factory, connection_state=demo_connection_state())

    response = client.post(
        "/api/v1/trading/signals",
        json={
            "symbol_code": "GBPUSD",
            "timeframe": "5m",
            "side": "short",
            "confidence": 73.0,
            "entry_price": 1.2700,
            "stop_loss": 1.2750,
            "take_profit": 1.2600,
            "model_type": "supervised",
        },
    )

    assert response.status_code == 409
    assert "symbol_not_approved" in response.json()["detail"]

    with session_scope(session_factory) as session:
        signals = session.query(PaperTradeSignal).all()
        audit_logs = session.query(AuditLog).all()

    assert signals == []
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.BLOCKED
    engine.dispose()


def test_sync_trading_state_fills_submitted_order_and_creates_position(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_sync_fill.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, approved_model_id = seed_approved_symbol(session, code="EURUSD")
        signal = PaperTradeSignal(
            approved_model_id=approved_model_id,
            symbol_id=symbol_id,
            timeframe=Timeframe.M1,
            side=TradeSide.LONG,
            status=SignalStatus.EXECUTED,
            signal_time=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
            confidence=Decimal("74.0"),
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
        )
        session.add(signal)
        session.flush()
        session.add(
            PaperTradeOrder(
                signal_id=signal.id,
                symbol_id=symbol_id,
                side=TradeSide.LONG,
                status=OrderStatus.SUBMITTED,
                broker_order_id="9001",
                requested_quantity=Decimal("0.25"),
                requested_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                submitted_at=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
            )
        )

    client = build_test_client(
        session_factory,
        connection_state=demo_connection_state(),
        order_history=[
            MT5HistoricalOrderRecord(
                broker_order_id="9001",
                status="filled",
                execution_price=Decimal("1.1015"),
                execution_quantity=Decimal("0.25"),
                execution_time=datetime(2026, 4, 4, 13, 2, tzinfo=UTC),
                comment="signal:1",
                raw_record={"ticket": 9001},
            )
        ],
        open_positions=[
            MT5PositionRecord(
                broker_order_id="9001",
                symbol_code="EURUSD",
                side="long",
                quantity=Decimal("0.25"),
                open_price=Decimal("1.1015"),
                current_price=Decimal("1.1030"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                opened_at=datetime(2026, 4, 4, 13, 2, tzinfo=UTC),
                unrealized_pnl=Decimal("0.00038"),
                comment="signal:1",
                raw_record={"ticket": 9001},
            )
        ],
    )
    response = client.post("/api/v1/trading/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["orders_updated"] == 1
    assert body["positions_updated"] == 2
    assert body["executions_created"] == 1
    assert body["history_records_seen"] == 1
    assert body["broker_positions_seen"] == 1

    with session_scope(session_factory) as session:
        order = session.get(PaperTradeOrder, 1)
        position = session.query(PaperTradePosition).one()
        executions = session.query(TradeExecution).all()
        account = session.query(MT5Account).one()
        snapshots = session.query(EquitySnapshot).all()
        audit_logs = session.query(AuditLog).filter(AuditLog.action == "paper_trading_sync").all()

    assert order is not None
    assert order.status is OrderStatus.FILLED
    assert order.filled_price == Decimal("1.1015")
    assert position.status is PositionStatus.OPEN
    assert position.unrealized_pnl == Decimal("0.00038")
    assert len(executions) == 1
    assert executions[0].execution_type == "open"
    assert len(snapshots) == 1
    assert snapshots[0].balance == Decimal("10000.00")
    assert snapshots[0].equity == Decimal("10000.38")
    assert snapshots[0].open_positions_count == 1
    assert account.details["last_synced_by"] == "test-operator"
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.SUCCESS
    engine.dispose()


def test_sync_trading_state_closes_position_from_broker_history(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_sync_close.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, approved_model_id = seed_approved_symbol(session, code="USDJPY")
        signal = PaperTradeSignal(
            approved_model_id=approved_model_id,
            symbol_id=symbol_id,
            timeframe=Timeframe.M5,
            side=TradeSide.SHORT,
            status=SignalStatus.EXECUTED,
            signal_time=datetime(2026, 4, 4, 12, 5, tzinfo=UTC),
            confidence=Decimal("77.0"),
            entry_price=Decimal("151.0"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
        )
        session.add(signal)
        session.flush()
        opening_order = PaperTradeOrder(
            signal_id=signal.id,
            symbol_id=symbol_id,
            side=TradeSide.SHORT,
            status=OrderStatus.FILLED,
            broker_order_id="1002",
            requested_quantity=Decimal("0.10"),
            filled_quantity=Decimal("0.10"),
            requested_price=Decimal("151.0"),
            filled_price=Decimal("150.9"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
            submitted_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
            filled_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
        )
        session.add(opening_order)
        session.flush()
        position = PaperTradePosition(
            order_id=opening_order.id,
            symbol_id=symbol_id,
            side=TradeSide.SHORT,
            status=PositionStatus.OPEN,
            opened_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
            quantity=Decimal("0.10"),
            open_price=Decimal("150.9"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
        )
        session.add(position)
        session.flush()
        session.add(
            PaperTradeOrder(
                signal_id=signal.id,
                symbol_id=symbol_id,
                side=TradeSide.LONG,
                status=OrderStatus.SUBMITTED,
                broker_order_id="2002",
                requested_quantity=Decimal("0.10"),
                requested_price=Decimal("150.9"),
                stop_loss=Decimal("151.5"),
                take_profit=Decimal("150.0"),
                submitted_at=datetime(2026, 4, 4, 14, 0, tzinfo=UTC),
            )
        )

    client = build_test_client(
        session_factory,
        connection_state=demo_connection_state(),
        order_history=[
            MT5HistoricalOrderRecord(
                broker_order_id="2002",
                status="filled",
                execution_price=Decimal("150.4"),
                execution_quantity=Decimal("0.10"),
                execution_time=datetime(2026, 4, 4, 14, 1, tzinfo=UTC),
                comment="close_position:1",
                raw_record={"ticket": 2002},
            )
        ],
        open_positions=[],
    )
    response = client.post("/api/v1/trading/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["orders_updated"] == 1
    assert body["positions_updated"] == 1
    assert body["executions_created"] == 1

    with session_scope(session_factory) as session:
        closing_order = session.get(PaperTradeOrder, 2)
        position = session.get(PaperTradePosition, 1)
        executions = session.query(TradeExecution).order_by(TradeExecution.id.asc()).all()

    assert closing_order is not None
    assert closing_order.status is OrderStatus.FILLED
    assert position is not None
    assert position.status is PositionStatus.CLOSED
    assert position.close_price == Decimal("150.4")
    assert position.realized_pnl == Decimal("0.050")
    assert len(executions) == 1
    assert executions[0].execution_type == "close"
    engine.dispose()


def test_create_signal_blocks_live_account(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_signal_live.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        seed_approved_symbol(session, code="USDJPY")

    client = build_test_client(
        session_factory,
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
    )

    response = client.post(
        "/api/v1/trading/signals",
        json={
            "symbol_code": "USDJPY",
            "timeframe": "15m",
            "side": "long",
            "confidence": 78.0,
            "entry_price": 151.0,
            "stop_loss": 150.5,
            "take_profit": 152.2,
            "model_type": "supervised",
        },
    )

    assert response.status_code == 409
    assert "live_account_blocked" in response.json()["detail"]
    engine.dispose()


def test_list_signals_filters_by_symbol_code(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_signal_list.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        eurusd_id, eurusd_approved_model_id = seed_approved_symbol(session, code="EURUSD")
        usdjpy_id, usdjpy_approved_model_id = seed_approved_symbol(session, code="USDJPY")
        session.add(
            PaperTradeSignal(
                approved_model_id=eurusd_approved_model_id,
                symbol_id=eurusd_id,
                timeframe=Timeframe.M1,
                side=TradeSide.LONG,
                status=SignalStatus.ACCEPTED,
                signal_time=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
                confidence=Decimal("74.0"),
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
            )
        )
        session.add(
            PaperTradeSignal(
                approved_model_id=usdjpy_approved_model_id,
                symbol_id=usdjpy_id,
                timeframe=Timeframe.M5,
                side=TradeSide.SHORT,
                status=SignalStatus.ACCEPTED,
                signal_time=datetime(2026, 4, 4, 12, 5, tzinfo=UTC),
                confidence=Decimal("77.0"),
                entry_price=Decimal("151.0"),
                stop_loss=Decimal("151.5"),
                take_profit=Decimal("150.0"),
            )
        )

    client = build_test_client(session_factory, connection_state=demo_connection_state())
    response = client.get("/api/v1/trading/signals", params={"symbol_code": "EURUSD"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["signals"]) == 1
    assert body["signals"][0]["symbol_code"] == "EURUSD"
    engine.dispose()


def test_create_order_from_signal_persists_order_position_and_execution(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_order_submit.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, approved_model_id = seed_approved_symbol(session, code="EURUSD")
        session.add(
            PaperTradeSignal(
                approved_model_id=approved_model_id,
                symbol_id=symbol_id,
                timeframe=Timeframe.M1,
                side=TradeSide.LONG,
                status=SignalStatus.ACCEPTED,
                signal_time=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
                confidence=Decimal("74.0"),
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
            )
        )

    client = build_test_client(session_factory, connection_state=demo_connection_state())
    response = client.post("/api/v1/trading/orders", json={"signal_id": 1, "quantity": 0.25})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "filled"
    assert body["symbol_code"] == "EURUSD"
    assert body["broker_order_id"] == "1001"

    with session_scope(session_factory) as session:
        orders = session.query(PaperTradeOrder).all()
        positions = session.query(PaperTradePosition).all()
        executions = session.query(TradeExecution).all()
        signals = session.query(PaperTradeSignal).all()
        audit_logs = session.query(AuditLog).filter(AuditLog.action == "paper_trade_order").all()

    assert len(orders) == 1
    assert orders[0].status is OrderStatus.FILLED
    assert len(positions) == 1
    assert len(executions) == 1
    assert signals[0].status is SignalStatus.EXECUTED
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.SUCCESS
    engine.dispose()


def test_create_order_rejects_signal_when_broker_rejects_submission(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_order_reject.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, approved_model_id = seed_approved_symbol(session, code="USDJPY")
        session.add(
            PaperTradeSignal(
                approved_model_id=approved_model_id,
                symbol_id=symbol_id,
                timeframe=Timeframe.M5,
                side=TradeSide.SHORT,
                status=SignalStatus.ACCEPTED,
                signal_time=datetime(2026, 4, 4, 12, 5, tzinfo=UTC),
                confidence=Decimal("77.0"),
                entry_price=Decimal("151.0"),
                stop_loss=Decimal("151.5"),
                take_profit=Decimal("150.0"),
            )
        )

    client = build_test_client(
        session_factory,
        connection_state=demo_connection_state(),
        order_result=MT5OrderResult(
            accepted=False,
            filled=False,
            broker_order_id=None,
            execution_price=None,
            execution_quantity=None,
            execution_time=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
            rejection_reason="broker_rejected",
            comment="rejected",
            raw_result={"retcode": 10021},
        ),
    )
    response = client.post("/api/v1/trading/orders", json={"signal_id": 1, "quantity": 0.10})

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["rejection_reason"] == "broker_rejected"

    with session_scope(session_factory) as session:
        orders = session.query(PaperTradeOrder).all()
        positions = session.query(PaperTradePosition).all()
        signal = session.get(PaperTradeSignal, 1)

    assert len(orders) == 1
    assert orders[0].status is OrderStatus.REJECTED
    assert positions == []
    assert signal is not None
    assert signal.status is SignalStatus.REJECTED
    engine.dispose()


def test_list_orders_and_positions_filter_by_symbol_code(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_order_position_list.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        eurusd_id, eurusd_approved_model_id = seed_approved_symbol(session, code="EURUSD")
        usdjpy_id, usdjpy_approved_model_id = seed_approved_symbol(session, code="USDJPY")
        eurusd_signal = PaperTradeSignal(
            approved_model_id=eurusd_approved_model_id,
            symbol_id=eurusd_id,
            timeframe=Timeframe.M1,
            side=TradeSide.LONG,
            status=SignalStatus.EXECUTED,
            signal_time=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
            confidence=Decimal("74.0"),
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
        )
        usdjpy_signal = PaperTradeSignal(
            approved_model_id=usdjpy_approved_model_id,
            symbol_id=usdjpy_id,
            timeframe=Timeframe.M5,
            side=TradeSide.SHORT,
            status=SignalStatus.EXECUTED,
            signal_time=datetime(2026, 4, 4, 12, 5, tzinfo=UTC),
            confidence=Decimal("77.0"),
            entry_price=Decimal("151.0"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
        )
        session.add_all([eurusd_signal, usdjpy_signal])
        session.flush()

        eurusd_order = PaperTradeOrder(
            signal_id=eurusd_signal.id,
            symbol_id=eurusd_id,
            side=TradeSide.LONG,
            status=OrderStatus.FILLED,
            broker_order_id="101",
            requested_quantity=Decimal("0.25"),
            filled_quantity=Decimal("0.25"),
            requested_price=Decimal("1.1000"),
            filled_price=Decimal("1.1010"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            submitted_at=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
            filled_at=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
        )
        usdjpy_order = PaperTradeOrder(
            signal_id=usdjpy_signal.id,
            symbol_id=usdjpy_id,
            side=TradeSide.SHORT,
            status=OrderStatus.FILLED,
            broker_order_id="102",
            requested_quantity=Decimal("0.10"),
            filled_quantity=Decimal("0.10"),
            requested_price=Decimal("151.0"),
            filled_price=Decimal("150.9"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
            submitted_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
            filled_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
        )
        session.add_all([eurusd_order, usdjpy_order])
        session.flush()
        session.add(
            PaperTradePosition(
                order_id=eurusd_order.id,
                symbol_id=eurusd_id,
                side=TradeSide.LONG,
                opened_at=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
                quantity=Decimal("0.25"),
                open_price=Decimal("1.1010"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
            )
        )
        session.add(
            PaperTradePosition(
                order_id=usdjpy_order.id,
                symbol_id=usdjpy_id,
                side=TradeSide.SHORT,
                opened_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
                quantity=Decimal("0.10"),
                open_price=Decimal("150.9"),
                stop_loss=Decimal("151.5"),
                take_profit=Decimal("150.0"),
            )
        )

    client = build_test_client(session_factory, connection_state=demo_connection_state())
    orders_response = client.get("/api/v1/trading/orders", params={"symbol_code": "EURUSD"})
    positions_response = client.get("/api/v1/trading/positions", params={"symbol_code": "EURUSD"})

    assert orders_response.status_code == 200
    assert len(orders_response.json()["orders"]) == 1
    assert orders_response.json()["orders"][0]["symbol_code"] == "EURUSD"
    assert positions_response.status_code == 200
    assert len(positions_response.json()["positions"]) == 1
    assert positions_response.json()["positions"][0]["symbol_code"] == "EURUSD"
    engine.dispose()


def test_close_position_persists_closing_order_and_updates_position(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_close_position.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, approved_model_id = seed_approved_symbol(session, code="EURUSD")
        signal = PaperTradeSignal(
            approved_model_id=approved_model_id,
            symbol_id=symbol_id,
            timeframe=Timeframe.M1,
            side=TradeSide.LONG,
            status=SignalStatus.EXECUTED,
            signal_time=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
            confidence=Decimal("74.0"),
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
        )
        session.add(signal)
        session.flush()
        order = PaperTradeOrder(
            signal_id=signal.id,
            symbol_id=symbol_id,
            side=TradeSide.LONG,
            status=OrderStatus.FILLED,
            broker_order_id="1001",
            requested_quantity=Decimal("0.25"),
            filled_quantity=Decimal("0.25"),
            requested_price=Decimal("1.1000"),
            filled_price=Decimal("1.1010"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            submitted_at=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
            filled_at=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
        )
        session.add(order)
        session.flush()
        position = PaperTradePosition(
            order_id=order.id,
            symbol_id=symbol_id,
            side=TradeSide.LONG,
            status=PositionStatus.OPEN,
            opened_at=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
            quantity=Decimal("0.25"),
            open_price=Decimal("1.1010"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
        )
        session.add(position)

    client = build_test_client(
        session_factory,
        connection_state=demo_connection_state(),
        order_result=MT5OrderResult(
            accepted=True,
            filled=True,
            broker_order_id="2001",
            execution_price=Decimal("1.1080"),
            execution_quantity=Decimal("0.25"),
            execution_time=datetime(2026, 4, 4, 14, 0, tzinfo=UTC),
            raw_result={"retcode": 10009},
        ),
    )
    response = client.post("/api/v1/trading/positions/1/close")

    assert response.status_code == 200
    body = response.json()
    assert body["position"]["status"] == "closed"
    assert body["position"]["close_price"] == 1.108
    assert body["closing_order"]["status"] == "filled"
    assert body["closing_order"]["broker_order_id"] == "2001"

    with session_scope(session_factory) as session:
        position = session.get(PaperTradePosition, 1)
        orders = session.query(PaperTradeOrder).order_by(PaperTradeOrder.id.asc()).all()
        executions = session.query(TradeExecution).order_by(TradeExecution.id.asc()).all()

    assert position is not None
    assert position.status is PositionStatus.CLOSED
    assert position.realized_pnl == Decimal("0.00175")
    assert len(orders) == 2
    assert orders[1].status is OrderStatus.FILLED
    assert len(executions) == 1
    assert executions[0].execution_type == "close"
    engine.dispose()


def test_close_position_returns_rejected_closing_order_when_broker_rejects(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_close_reject.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, approved_model_id = seed_approved_symbol(session, code="USDJPY")
        signal = PaperTradeSignal(
            approved_model_id=approved_model_id,
            symbol_id=symbol_id,
            timeframe=Timeframe.M5,
            side=TradeSide.SHORT,
            status=SignalStatus.EXECUTED,
            signal_time=datetime(2026, 4, 4, 12, 5, tzinfo=UTC),
            confidence=Decimal("77.0"),
            entry_price=Decimal("151.0"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
        )
        session.add(signal)
        session.flush()
        order = PaperTradeOrder(
            signal_id=signal.id,
            symbol_id=symbol_id,
            side=TradeSide.SHORT,
            status=OrderStatus.FILLED,
            broker_order_id="1002",
            requested_quantity=Decimal("0.10"),
            filled_quantity=Decimal("0.10"),
            requested_price=Decimal("151.0"),
            filled_price=Decimal("150.9"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
            submitted_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
            filled_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
        )
        session.add(order)
        session.flush()
        position = PaperTradePosition(
            order_id=order.id,
            symbol_id=symbol_id,
            side=TradeSide.SHORT,
            status=PositionStatus.OPEN,
            opened_at=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
            quantity=Decimal("0.10"),
            open_price=Decimal("150.9"),
            stop_loss=Decimal("151.5"),
            take_profit=Decimal("150.0"),
        )
        session.add(position)

    client = build_test_client(
        session_factory,
        connection_state=demo_connection_state(),
        order_result=MT5OrderResult(
            accepted=False,
            filled=False,
            broker_order_id=None,
            execution_price=None,
            execution_quantity=None,
            execution_time=datetime(2026, 4, 4, 14, 5, tzinfo=UTC),
            rejection_reason="close_rejected",
            comment="close_rejected",
            raw_result={"retcode": 10021},
        ),
    )
    response = client.post("/api/v1/trading/positions/1/close")

    assert response.status_code == 200
    assert response.json()["position"]["status"] == "open"
    assert response.json()["closing_order"]["status"] == "rejected"
    assert response.json()["closing_order"]["rejection_reason"] == "close_rejected"

    with session_scope(session_factory) as session:
        position = session.get(PaperTradePosition, 1)
        orders = session.query(PaperTradeOrder).order_by(PaperTradeOrder.id.asc()).all()

    assert position is not None
    assert position.status is PositionStatus.OPEN
    assert len(orders) == 2
    assert orders[1].status is OrderStatus.REJECTED
    engine.dispose()


def build_test_client(
    session_factory,
    *,
    connection_state: MT5ConnectionState,
    order_result: MT5OrderResult | None = None,
    order_history: list[MT5HistoricalOrderRecord] | None = None,
    open_positions: list[MT5PositionRecord] | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(trading_router, prefix="/api/v1")
    app.state.event_broadcaster = EventBroadcaster()
    app.dependency_overrides[get_api_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[require_authenticated_principal] = lambda: AuthPrincipal(
        subject="test-operator",
        roles=("operator",),
        auth_mode="disabled",
    )
    app.dependency_overrides[get_mt5_gateway] = lambda: FakeMT5Gateway(
        connection_state,
        order_result=order_result,
        order_history=order_history,
        open_positions=open_positions,
    )

    def override_db() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def seed_approved_symbol(session, *, code: str) -> tuple[int, int]:
    symbol = Symbol(code=code, base_currency=code[:3], quote_currency=code[3:], provider="mt5")
    session.add(symbol)
    session.flush()
    approved_model = ApprovedModel(
        symbol_id=symbol.id,
        supervised_model_id=symbol.id,
        model_type=ModelType.SUPERVISED.value,
        confidence=Decimal("75.0"),
        risk_to_reward=Decimal("2.5"),
        is_active=True,
    )
    session.add(approved_model)
    session.flush()
    return symbol.id, approved_model.id


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
        balance=Decimal("10000.00"),
        equity=Decimal("10000.38"),
        margin=Decimal("250.00"),
        free_margin=Decimal("9750.38"),
    )
