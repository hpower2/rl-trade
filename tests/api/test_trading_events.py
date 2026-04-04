"""Trading event emission tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_api_settings, get_db_session, get_mt5_gateway, require_authenticated_principal
from rl_trade_api.api.routes.events import router as events_router
from rl_trade_api.api.v1.routes.trading import router as trading_router
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings
from rl_trade_data import (
    ApprovedModel,
    Base,
    PaperTradeOrder,
    PaperTradePosition,
    PaperTradeSignal,
    Symbol,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import ConnectionStatus, ModelType, OrderStatus, PositionStatus, SignalStatus, Timeframe, TradeSide
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

    def list_order_history(
        self,
        settings: Settings,
        *,
        start_time: datetime,
        end_time: datetime | None = None,
    ) -> list[MT5HistoricalOrderRecord]:
        return list(self._order_history)

    def list_open_positions(self, settings: Settings) -> list[MT5PositionRecord]:
        return list(self._open_positions)


def test_create_signal_emits_live_signal_event(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_events_signal.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        seed_approved_symbol(session, code="EURUSD")

    client = build_test_client(session_factory, connection_state=demo_connection_state())

    with client.websocket_connect("/ws/events?topics=signal_event") as websocket:
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
                "rationale": {"source": "event_test"},
            },
        )
        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["delivery"] == "live"
    assert message["event"]["event_type"] == "signal_event"
    assert message["event"]["entity_type"] == "paper_trade_signal"
    assert message["event"]["entity_id"] == "1"
    assert message["event"]["payload"]["signal_id"] == 1
    assert message["event"]["payload"]["status"] == "accepted"
    assert message["event"]["payload"]["symbol_code"] == "EURUSD"
    assert message["event"]["payload"]["source"] == "api_request"
    assert "order" not in message["event"]["payload"]
    engine.dispose()


def test_create_order_emits_signal_and_position_events_for_filled_order(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_events_order.sqlite'}"
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

    with client.websocket_connect("/ws/events?topics=signal_event,position_update") as websocket:
        response = client.post("/api/v1/trading/orders", json={"signal_id": 1, "quantity": 0.25})
        signal_message = websocket.receive_json()
        position_message = websocket.receive_json()

    assert response.status_code == 200
    assert signal_message["event"]["event_type"] == "signal_event"
    assert signal_message["event"]["payload"]["signal_id"] == 1
    assert signal_message["event"]["payload"]["status"] == "executed"
    assert signal_message["event"]["payload"]["source"] == "order_submission"
    assert signal_message["event"]["payload"]["order"]["order_id"] == 1
    assert signal_message["event"]["payload"]["order"]["status"] == "filled"

    assert position_message["event"]["event_type"] == "position_update"
    assert position_message["event"]["entity_type"] == "paper_trade_position"
    assert position_message["event"]["entity_id"] == "1"
    assert position_message["event"]["payload"]["position_id"] == 1
    assert position_message["event"]["payload"]["status"] == "open"
    assert position_message["event"]["payload"]["source"] == "order_fill"
    assert position_message["event"]["payload"]["order"]["order_id"] == 1
    assert position_message["event"]["payload"]["order"]["status"] == "filled"
    engine.dispose()


def test_close_position_emits_closed_position_event(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_events_close.sqlite'}"
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
            filled_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            submitted_at=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
            filled_at=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
        )
        session.add(order)
        session.flush()
        session.add(
            PaperTradePosition(
                order_id=order.id,
                symbol_id=symbol_id,
                side=TradeSide.LONG,
                status=PositionStatus.OPEN,
                opened_at=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
                quantity=Decimal("0.25"),
                open_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                unrealized_pnl=Decimal("0.0002"),
            )
        )

    close_result = MT5OrderResult(
        accepted=True,
        filled=True,
        broker_order_id="2001",
        execution_price=Decimal("1.1010"),
        execution_quantity=Decimal("0.25"),
        execution_time=datetime(2026, 4, 4, 13, 5, tzinfo=UTC),
        raw_result={"retcode": 10009},
    )
    client = build_test_client(
        session_factory,
        connection_state=demo_connection_state(),
        order_result=close_result,
    )

    with client.websocket_connect("/ws/events?topics=position_update") as websocket:
        response = client.post("/api/v1/trading/positions/1/close")
        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["event"]["event_type"] == "position_update"
    assert message["event"]["entity_id"] == "1"
    assert message["event"]["payload"]["position_id"] == 1
    assert message["event"]["payload"]["status"] == "closed"
    assert message["event"]["payload"]["source"] == "position_close"
    assert message["event"]["payload"]["close_price"] == 1.101
    assert message["event"]["payload"]["realized_pnl"] == 0.00025
    assert message["event"]["payload"]["order"]["order_id"] == 2
    assert message["event"]["payload"]["order"]["status"] == "filled"
    engine.dispose()


def test_sync_emits_position_and_equity_events(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_events_sync.sqlite'}"
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

    with client.websocket_connect("/ws/events?topics=position_update,equity_update") as websocket:
        response = client.post("/api/v1/trading/sync")
        position_message = websocket.receive_json()
        equity_message = websocket.receive_json()

    assert response.status_code == 200
    assert position_message["event"]["event_type"] == "position_update"
    assert position_message["event"]["entity_type"] == "paper_trade_position"
    assert position_message["event"]["payload"]["position_id"] == 1
    assert position_message["event"]["payload"]["status"] == "open"
    assert position_message["event"]["payload"]["source"] == "sync_reconciliation"
    assert position_message["event"]["payload"]["order"]["order_id"] == 1
    assert position_message["event"]["payload"]["order"]["status"] == "filled"

    assert equity_message["event"]["event_type"] == "equity_update"
    assert equity_message["event"]["entity_type"] == "equity_snapshot"
    assert equity_message["event"]["payload"]["snapshot_id"] == 1
    assert equity_message["event"]["payload"]["account_login"] == 123456
    assert equity_message["event"]["payload"]["balance"] == 10000.0
    assert equity_message["event"]["payload"]["equity"] == 10000.38
    assert equity_message["event"]["payload"]["open_positions_count"] == 1
    assert equity_message["event"]["payload"]["details"]["total_unrealized_pnl"] == 0.00038
    assert equity_message["event"]["payload"]["source"] == "sync_reconciliation"
    engine.dispose()


def test_blocked_signal_emits_alert_event(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_events_signal_alert.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        session.add(Symbol(code="GBPUSD", base_currency="GBP", quote_currency="USD", provider="mt5"))

    client = build_test_client(session_factory, connection_state=demo_connection_state())

    with client.websocket_connect("/ws/events?topics=alert") as websocket:
        response = client.post(
            "/api/v1/trading/signals",
            json={
                "symbol_code": "GBPUSD",
                "timeframe": "1m",
                "side": "long",
                "confidence": 74.0,
                "entry_price": 1.2500,
                "stop_loss": 1.2450,
                "take_profit": 1.2600,
                "model_type": "supervised",
                "rationale": {"source": "blocked_event_test"},
            },
        )
        message = websocket.receive_json()

    assert response.status_code == 409
    assert message["event"]["event_type"] == "alert"
    assert message["event"]["entity_type"] == "paper_trade_signal"
    assert message["event"]["payload"]["severity"] == "warning"
    assert message["event"]["payload"]["alert_code"] == "paper_trade_signal_blocked"
    assert message["event"]["payload"]["symbol_code"] == "GBPUSD"
    assert "symbol_not_approved" in message["event"]["payload"]["reasons"]
    assert message["event"]["payload"]["operation"] == "create_signal"
    engine.dispose()


def test_blocked_start_emits_alert_event(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_events_start_alert.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    client = build_test_client(session_factory, connection_state=live_connection_state())

    with client.websocket_connect("/ws/events?topics=alert") as websocket:
        response = client.post("/api/v1/trading/start")
        message = websocket.receive_json()

    assert response.status_code == 409
    assert message["event"]["event_type"] == "alert"
    assert message["event"]["entity_type"] == "paper_trading_runtime"
    assert message["event"]["entity_id"] == "default"
    assert message["event"]["payload"]["severity"] == "warning"
    assert message["event"]["payload"]["alert_code"] == "paper_trading_start_blocked"
    assert message["event"]["payload"]["reason"] == "live_account_blocked"
    assert message["event"]["payload"]["operation"] == "start_trading"
    engine.dispose()


def test_blocked_sync_emits_alert_event(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'trading_events_sync_alert.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    client = build_test_client(session_factory, connection_state=live_connection_state())

    with client.websocket_connect("/ws/events?topics=alert") as websocket:
        response = client.post("/api/v1/trading/sync")
        message = websocket.receive_json()

    assert response.status_code == 409
    assert message["event"]["event_type"] == "alert"
    assert message["event"]["entity_type"] == "paper_trading_sync"
    assert message["event"]["entity_id"] == "default"
    assert message["event"]["payload"]["severity"] == "warning"
    assert message["event"]["payload"]["alert_code"] == "paper_trading_sync_blocked"
    assert message["event"]["payload"]["reason"] == "live_account_blocked"
    assert message["event"]["payload"]["operation"] == "sync_trading_state"
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
    app.include_router(events_router)
    app.include_router(trading_router, prefix="/api/v1")
    app.state.settings = Settings(_env_file=None)
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


def live_connection_state() -> MT5ConnectionState:
    return MT5ConnectionState(
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
        balance=Decimal("10000.00"),
        equity=Decimal("10000.00"),
        margin=Decimal("250.00"),
        free_margin=Decimal("9750.00"),
    )
