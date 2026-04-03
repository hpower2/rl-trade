"""Symbol normalization and validation provider tests."""

from __future__ import annotations

from types import SimpleNamespace

from rl_trade_common.settings import Settings
from rl_trade_trading import MT5Gateway, normalize_symbol_input


class FakeMT5ValidationModule:
    def __init__(self, *, direct_match: object | None = None, symbols: list[object] | None = None) -> None:
        self._direct_match = direct_match
        self._symbols = symbols or []

    def initialize(self, **kwargs) -> bool:
        return True

    def symbol_info(self, symbol: str) -> object | None:
        return self._direct_match

    def symbols_get(self) -> list[object]:
        return self._symbols

    def last_error(self) -> tuple[int, str]:
        return (0, "ok")

    def shutdown(self) -> None:
        return None


def test_normalize_symbol_input_removes_common_separators() -> None:
    assert normalize_symbol_input(" eur/usd ") == "EURUSD"
    assert normalize_symbol_input("gbp_jpy") == "GBPJPY"
    assert normalize_symbol_input("usd-cad") == "USDCAD"


def test_mt5_gateway_validate_symbol_returns_normalized_valid_match() -> None:
    module = FakeMT5ValidationModule(
        symbols=[
            SimpleNamespace(
                name="EURUSDm",
                description="Euro vs US Dollar",
                path="Forex\\Majors",
                visible=True,
                spread=11,
            )
        ]
    )
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="1",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    decision = gateway.validate_symbol(settings, "eur/usd")

    assert decision.is_valid is True
    assert decision.normalized_input == "EURUSD"
    assert decision.normalized_symbol == "EURUSDm"
    assert decision.base_currency == "EUR"
    assert decision.quote_currency == "USD"
    assert decision.details["matched_by"] == "prefix"


def test_mt5_gateway_validate_symbol_rejects_invalid_or_unknown_symbols() -> None:
    module = FakeMT5ValidationModule(symbols=[])
    gateway = MT5Gateway(module_loader=lambda: module)
    settings = Settings(
        _env_file=None,
        mt5_login="1",
        mt5_password="secret",
        mt5_server="Broker-Demo",
    )

    invalid_format = gateway.validate_symbol(settings, "eur$")
    missing_symbol = gateway.validate_symbol(settings, "AUDCAD")

    assert invalid_format.is_valid is False
    assert invalid_format.reason == "invalid_format"
    assert missing_symbol.is_valid is False
    assert missing_symbol.reason == "symbol_not_found"
