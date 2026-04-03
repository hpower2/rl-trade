"""MT5 gateway tests."""

from __future__ import annotations

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
        initialize_ok: bool = True,
        error: tuple[int, str] = (0, "ok"),
    ) -> None:
        self._account = account
        self._symbols = symbols or []
        self._initialize_ok = initialize_ok
        self._error = error
        self.shutdown_called = False

    def initialize(self, **kwargs) -> bool:
        return self._initialize_ok

    def account_info(self) -> object | None:
        return self._account

    def symbols_get(self) -> list[object]:
        return self._symbols

    def last_error(self) -> tuple[int, str]:
        return self._error

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
