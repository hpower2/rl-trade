"""MT5 gateway tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from rl_trade_common.settings import Settings
from rl_trade_data.models.enums import ConnectionStatus
from rl_trade_trading import MT5Gateway, MT5IntegrationError


class FakeMT5Module:
    def __init__(
        self,
        *,
        account: object | None = None,
        symbols: list[object] | None = None,
        order_result: object | None = None,
        history_orders: list[object] | None = None,
        positions: list[object] | None = None,
        initialize_ok: bool = True,
        error: tuple[int, str] = (0, "ok"),
    ) -> None:
        self._account = account
        self._symbols = symbols or []
        self._order_result = order_result
        self._history_orders = history_orders or []
        self._positions = positions or []
        self._initialize_ok = initialize_ok
        self._error = error
        self.shutdown_called = False
        self.TRADE_ACTION_DEAL = 1
        self.ORDER_TYPE_BUY = 0
        self.ORDER_TYPE_SELL = 1
        self.ORDER_TIME_GTC = 0
        self.ORDER_FILLING_IOC = 1
        self.TRADE_RETCODE_DONE = 10009
        self.TRADE_RETCODE_PLACED = 10008
        self.TRADE_RETCODE_DONE_PARTIAL = 10010
        self.ORDER_STATE_FILLED = 4
        self.ORDER_STATE_CANCELED = 5
        self.ORDER_STATE_REJECTED = 6
        self.POSITION_TYPE_BUY = 0
        self.POSITION_TYPE_SELL = 1

    def initialize(self, **kwargs) -> bool:
        return self._initialize_ok

    def account_info(self) -> object | None:
        return self._account

    def symbols_get(self) -> list[object]:
        return self._symbols

    def last_error(self) -> tuple[int, str]:
        return self._error

    def order_send(self, request: dict[str, object]) -> object | None:
        self.last_order_request = request
        return self._order_result

    def history_orders_get(self, start_time, end_time) -> list[object]:
        self.last_history_window = (start_time, end_time)
        return self._history_orders

    def positions_get(self) -> list[object]:
        return self._positions

    def shutdown(self) -> None:
        self.shutdown_called = True


def test_mt5_connection_state_allows_demo_accounts() -> None:
    module = FakeMT5Module(
        account=SimpleNamespace(
            login=123456,
            server="Broker-Demo",
            name="Trader Demo",
            currency="USD",
            leverage=100,
            balance=10000.0,
            equity=10025.5,
            margin=250.0,
            margin_free=9775.5,
            trade_allowed=True,
        )
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="123456",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    state = gateway.get_connection_state(settings)

    assert state.status == ConnectionStatus.CONNECTED
    assert state.is_demo is True
    assert state.paper_trading_allowed is True
    assert state.reason is None
    assert state.balance == Decimal("10000.0")
    assert state.equity == Decimal("10025.5")
    assert state.margin == Decimal("250.0")
    assert state.free_margin == Decimal("9775.5")
    assert module.shutdown_called is True


def test_mt5_connection_state_blocks_live_accounts_even_when_connected() -> None:
    module = FakeMT5Module(
        account=SimpleNamespace(
            login=654321,
            server="Broker-Live",
            name="Trader Live",
            currency="EUR",
            leverage=50,
            trade_allowed=True,
        )
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="654321",
        mt5_password="secret",
        mt5_server="Broker-Live",
    )

    state = gateway.get_connection_state(settings)

    assert state.status == ConnectionStatus.CONNECTED
    assert state.is_demo is False
    assert state.paper_trading_allowed is False
    assert state.reason == "live_account_blocked"


def test_mt5_gateway_lists_symbols_and_filters_query() -> None:
    module = FakeMT5Module(
        account=SimpleNamespace(login=1, server="Broker-Demo", name="Trader Demo", trade_allowed=True),
        symbols=[
            SimpleNamespace(name="EURUSD", description="Euro vs Dollar", path="Forex\\Majors", visible=True, spread=12),
            SimpleNamespace(name="USDJPY", description="Dollar vs Yen", path="Forex\\Majors", visible=False, spread=9),
        ],
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="1",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    symbols = gateway.list_symbols(settings, query="eur")

    assert [symbol.code for symbol in symbols] == ["EURUSD"]
    assert module.shutdown_called is True


def test_mt5_gateway_raises_when_package_or_credentials_are_unavailable() -> None:
    unavailable_gateway = MT5Gateway(module_loader=lambda: (_ for _ in ()).throw(ModuleNotFoundError("MetaTrader5")))
    unconfigured_settings = Settings(_env_file=None)
    configured_settings = Settings(
        _env_file=None,
        mt5_login="1",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    disconnected = unavailable_gateway.get_connection_state(unconfigured_settings)

    assert disconnected.status == ConnectionStatus.DISCONNECTED
    assert disconnected.reason == "credentials_not_configured"

    try:
        unavailable_gateway.list_symbols(configured_settings)
    except MT5IntegrationError as exc:
        assert exc.reason == "mt5_package_not_installed"
    else:
        raise AssertionError("Expected MT5IntegrationError for unavailable package.")


def test_mt5_gateway_submits_paper_order() -> None:
    module = FakeMT5Module(
        account=SimpleNamespace(
            login=123456,
            server="Broker-Demo",
            name="Trader Demo",
            currency="USD",
            leverage=100,
            trade_allowed=True,
        ),
        order_result=SimpleNamespace(
            retcode=10009,
            order=789,
            deal=456,
            price=1.1010,
            volume=0.25,
            comment="ok",
        ),
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="123456",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    result = gateway.submit_paper_order(
        settings,
        symbol_code="EURUSD",
        side="long",
        quantity=Decimal("0.25"),
        price=Decimal("1.1000"),
        stop_loss=Decimal("1.0950"),
        take_profit=Decimal("1.1100"),
    )

    assert result.accepted is True
    assert result.filled is True
    assert result.broker_order_id == "789"
    assert result.execution_price == Decimal("1.101")
    assert module.last_order_request["symbol"] == "EURUSD"
    assert module.last_order_request["type"] == module.ORDER_TYPE_BUY


def test_mt5_gateway_returns_rejected_order_result() -> None:
    module = FakeMT5Module(
        account=SimpleNamespace(
            login=123456,
            server="Broker-Demo",
            name="Trader Demo",
            currency="USD",
            leverage=100,
            trade_allowed=True,
        ),
        order_result=SimpleNamespace(
            retcode=10021,
            order=0,
            deal=0,
            price=0.0,
            volume=0.0,
            comment="broker_rejected",
        ),
        error=(10021, "broker rejected"),
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="123456",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    result = gateway.submit_paper_order(
        settings,
        symbol_code="USDJPY",
        side="short",
        quantity=Decimal("0.10"),
        price=Decimal("151.0"),
        stop_loss=Decimal("151.5"),
        take_profit=Decimal("150.0"),
    )

    assert result.accepted is False
    assert result.filled is False
    assert result.rejection_reason == "broker_rejected"
    assert module.last_order_request["type"] == module.ORDER_TYPE_SELL


def test_mt5_gateway_lists_order_history_records() -> None:
    module = FakeMT5Module(
        account=SimpleNamespace(
            login=123456,
            server="Broker-Demo",
            name="Trader Demo",
            currency="USD",
            leverage=100,
            trade_allowed=True,
        ),
        history_orders=[
            SimpleNamespace(
                ticket=9001,
                state=4,
                price_current=1.1015,
                volume_initial=0.25,
                time_done=1_775_276_520,
                comment="signal:1",
            ),
            SimpleNamespace(
                ticket=9002,
                state=6,
                time_done=1_775_276_820,
                comment="broker_rejected",
            ),
        ],
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="123456",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    history = gateway.list_order_history(
        settings,
        start_time=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
    )

    assert len(history) == 2
    assert history[0].broker_order_id == "9001"
    assert history[0].status == "filled"
    assert history[0].comment == "signal:1"
    assert history[1].status == "rejected"
    assert history[1].rejection_reason == "broker_rejected"


def test_mt5_gateway_lists_open_positions() -> None:
    module = FakeMT5Module(
        account=SimpleNamespace(
            login=123456,
            server="Broker-Demo",
            name="Trader Demo",
            currency="USD",
            leverage=100,
            trade_allowed=True,
        ),
        positions=[
            SimpleNamespace(
                order=9001,
                symbol="EURUSD",
                type=0,
                volume=0.25,
                price_open=1.1015,
                price_current=1.1030,
                sl=1.0950,
                tp=1.1100,
                time=1_775_276_520,
                profit=0.00038,
                comment="signal:1",
            )
        ],
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="123456",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    positions = gateway.list_open_positions(settings)

    assert len(positions) == 1
    assert positions[0].broker_order_id == "9001"
    assert positions[0].symbol_code == "EURUSD"
    assert positions[0].side == "long"
    assert positions[0].unrealized_pnl == Decimal("0.00038")
