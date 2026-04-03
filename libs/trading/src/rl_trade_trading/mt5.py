"""MetaTrader 5 gateway and connection primitives."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from importlib import import_module
from typing import Any, Callable, Iterator

from rl_trade_common import Settings
from rl_trade_data.models.enums import ConnectionStatus
from rl_trade_data.models.enums import Timeframe
from rl_trade_trading.symbols import (
    SymbolValidationDecision,
    infer_forex_components,
    is_plausible_symbol_code,
    normalize_symbol_input,
)


class MT5IntegrationError(RuntimeError):
    """Raised when the MT5 integration cannot provide the requested data."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class MT5ConnectionState:
    status: ConnectionStatus
    account_login: int | None
    server_name: str | None
    account_name: str | None
    account_currency: str | None
    leverage: int | None
    is_demo: bool | None
    trade_allowed: bool | None
    paper_trading_allowed: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MT5SymbolRecord:
    code: str
    description: str | None = None
    path: str | None = None
    visible: bool | None = None
    spread: int | None = None


@dataclass(frozen=True, slots=True)
class MT5CandleRecord:
    timeframe: Timeframe
    candle_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    spread: int | None = None


def load_mt5_module() -> Any:
    return import_module("MetaTrader5")


class MT5Gateway:
    def __init__(self, module_loader: Callable[[], Any] | None = None) -> None:
        self._module_loader = module_loader or load_mt5_module

    def get_connection_state(self, settings: Settings) -> MT5ConnectionState:
        configuration_error = self._configuration_error(settings)
        if configuration_error is not None:
            return MT5ConnectionState(
                status=ConnectionStatus.DISCONNECTED,
                account_login=None,
                server_name=settings.mt5_server,
                account_name=None,
                account_currency=None,
                leverage=None,
                is_demo=None,
                trade_allowed=None,
                paper_trading_allowed=False,
                reason=configuration_error.reason,
                details=configuration_error.details,
            )

        try:
            with self._connected_module(settings) as module:
                account = module.account_info()
                if account is None:
                    raise MT5IntegrationError("account_info_unavailable", self._last_error_details(module))
                return self._build_connection_state(account)
        except MT5IntegrationError as exc:
            return MT5ConnectionState(
                status=ConnectionStatus.ERROR,
                account_login=None,
                server_name=settings.mt5_server,
                account_name=None,
                account_currency=None,
                leverage=None,
                is_demo=None,
                trade_allowed=None,
                paper_trading_allowed=False,
                reason=exc.reason,
                details=exc.details,
            )

    def list_symbols(self, settings: Settings, query: str | None = None) -> list[MT5SymbolRecord]:
        with self._connected_module(settings) as module:
            symbols = module.symbols_get()
            if symbols is None:
                raise MT5IntegrationError("symbols_unavailable", self._last_error_details(module))

            normalized_query = (query or "").strip().upper()
            records = [self._build_symbol_record(symbol) for symbol in symbols]
            if not normalized_query:
                return records

            return [
                record
                for record in records
                if normalized_query in record.code.upper()
                or normalized_query in (record.description or "").upper()
                or normalized_query in (record.path or "").upper()
            ]

    def validate_symbol(self, settings: Settings, requested_symbol: str) -> SymbolValidationDecision:
        normalized_input = normalize_symbol_input(requested_symbol)
        if not is_plausible_symbol_code(normalized_input):
            return SymbolValidationDecision(
                requested_symbol=requested_symbol,
                normalized_input=normalized_input,
                normalized_symbol=None,
                provider="mt5",
                is_valid=False,
                reason="invalid_format",
                details={"normalized_input": normalized_input},
            )

        with self._connected_module(settings) as module:
            record, matched_by = self._find_symbol_record(module, normalized_input)
            if record is None:
                return SymbolValidationDecision(
                    requested_symbol=requested_symbol,
                    normalized_input=normalized_input,
                    normalized_symbol=None,
                    provider="mt5",
                    is_valid=False,
                    reason="symbol_not_found",
                    details={"normalized_input": normalized_input},
                )

            base_currency, quote_currency = infer_forex_components(record.code)
            return SymbolValidationDecision(
                requested_symbol=requested_symbol,
                normalized_input=normalized_input,
                normalized_symbol=record.code,
                provider="mt5",
                is_valid=True,
                base_currency=base_currency,
                quote_currency=quote_currency,
                details={
                    "description": record.description,
                    "path": record.path,
                    "visible": record.visible,
                    "spread": record.spread,
                    "matched_by": matched_by,
                },
            )

    def fetch_candles(
        self,
        settings: Settings,
        *,
        symbol_code: str,
        timeframe: Timeframe,
        start_time: datetime,
        count: int,
    ) -> list[MT5CandleRecord]:
        with self._connected_module(settings) as module:
            mt5_timeframe = self._resolve_mt5_timeframe(module, timeframe)
            rates = module.copy_rates_from(symbol_code, mt5_timeframe, start_time, count)
            if rates is None:
                raise MT5IntegrationError("rates_unavailable", self._last_error_details(module))

            return [self._build_candle_record(timeframe, rate) for rate in rates]

    @contextmanager
    def _connected_module(self, settings: Settings) -> Iterator[Any]:
        configuration_error = self._configuration_error(settings)
        if configuration_error is not None:
            raise configuration_error

        try:
            module = self._module_loader()
        except ModuleNotFoundError as exc:
            raise MT5IntegrationError("mt5_package_not_installed") from exc

        try:
            initialized = module.initialize(
                path=settings.mt5_terminal_path,
                login=int(settings.mt5_login or 0),
                password=settings.mt5_password.get_secret_value() if settings.mt5_password else "",
                server=settings.mt5_server or "",
            )
        except Exception as exc:  # pragma: no cover - defensive integration guard
            raise MT5IntegrationError("initialize_exception", {"message": str(exc)}) from exc

        if not initialized:
            raise MT5IntegrationError("initialize_failed", self._last_error_details(module))

        try:
            yield module
        finally:
            module.shutdown()

    def _configuration_error(self, settings: Settings) -> MT5IntegrationError | None:
        if not settings.mt5_login or not settings.mt5_password or not settings.mt5_server:
            return MT5IntegrationError(
                "credentials_not_configured",
                {
                    "has_login": bool(settings.mt5_login),
                    "has_password": settings.mt5_password is not None,
                    "has_server": bool(settings.mt5_server),
                },
            )
        return None

    def _build_connection_state(self, account: Any) -> MT5ConnectionState:
        server_name = self._get_attr(account, "server")
        account_name = self._get_attr(account, "name")
        is_demo = self._infer_demo_account(server_name, account_name)
        trade_allowed = self._get_attr(account, "trade_allowed")
        paper_trading_allowed = bool(is_demo and trade_allowed)
        reason = None
        if is_demo is False:
            reason = "live_account_blocked"
        elif trade_allowed is False:
            reason = "trade_not_allowed"

        return MT5ConnectionState(
            status=ConnectionStatus.CONNECTED,
            account_login=self._get_attr(account, "login"),
            server_name=server_name,
            account_name=account_name,
            account_currency=self._get_attr(account, "currency"),
            leverage=self._get_attr(account, "leverage"),
            is_demo=is_demo,
            trade_allowed=trade_allowed,
            paper_trading_allowed=paper_trading_allowed,
            reason=reason,
            details={"terminal_connected": True},
        )

    def _build_symbol_record(self, symbol: Any) -> MT5SymbolRecord:
        return MT5SymbolRecord(
            code=str(self._get_attr(symbol, "name") or ""),
            description=self._get_attr(symbol, "description"),
            path=self._get_attr(symbol, "path"),
            visible=self._get_attr(symbol, "visible"),
            spread=self._get_attr(symbol, "spread"),
        )

    def _find_symbol_record(self, module: Any, normalized_input: str) -> tuple[MT5SymbolRecord | None, str | None]:
        symbol_info = getattr(module, "symbol_info", None)
        if callable(symbol_info):
            direct_match = symbol_info(normalized_input)
            if direct_match is not None:
                return self._build_symbol_record(direct_match), "exact"

        symbols = module.symbols_get()
        if symbols is None:
            raise MT5IntegrationError("symbols_unavailable", self._last_error_details(module))

        records = [self._build_symbol_record(symbol) for symbol in symbols]
        exact_match = next((record for record in records if record.code.upper() == normalized_input), None)
        if exact_match is not None:
            return exact_match, "exact"

        prefix_matches = [record for record in records if record.code.upper().startswith(normalized_input)]
        if not prefix_matches:
            return None, None

        prefix_matches.sort(key=lambda record: (record.visible is not True, len(record.code), record.code))
        return prefix_matches[0], "prefix"

    def _last_error_details(self, module: Any) -> dict[str, Any]:
        error = getattr(module, "last_error", lambda: None)()
        if isinstance(error, tuple) and len(error) == 2:
            return {"code": error[0], "message": error[1]}
        return {"message": str(error) if error is not None else "unknown"}

    def _infer_demo_account(self, server_name: str | None, account_name: str | None) -> bool | None:
        haystacks = [value.lower() for value in (server_name, account_name) if value]
        if not haystacks:
            return None
        return any("demo" in value for value in haystacks)

    def _get_attr(self, obj: Any, field_name: str) -> Any:
        return getattr(obj, field_name, None)

    def _build_candle_record(self, timeframe: Timeframe, rate: Any) -> MT5CandleRecord:
        candle_time_raw = self._get_rate_field(rate, "time")
        if candle_time_raw is None:
            raise MT5IntegrationError("rate_time_missing")

        candle_time = datetime.fromtimestamp(int(candle_time_raw), tz=timezone.utc)
        volume_value = self._get_rate_field(rate, "real_volume")
        if volume_value in (None, 0):
            volume_value = self._get_rate_field(rate, "tick_volume") or 0

        return MT5CandleRecord(
            timeframe=timeframe,
            candle_time=candle_time,
            open=Decimal(str(self._get_rate_field(rate, "open"))),
            high=Decimal(str(self._get_rate_field(rate, "high"))),
            low=Decimal(str(self._get_rate_field(rate, "low"))),
            close=Decimal(str(self._get_rate_field(rate, "close"))),
            volume=Decimal(str(volume_value)),
            spread=self._get_rate_field(rate, "spread"),
        )

    def _get_rate_field(self, rate: Any, field_name: str) -> Any:
        if isinstance(rate, dict):
            return rate.get(field_name)
        if hasattr(rate, field_name):
            return getattr(rate, field_name)
        try:
            return rate[field_name]
        except Exception:
            return None

    def _resolve_mt5_timeframe(self, module: Any, timeframe: Timeframe) -> Any:
        mapping = {
            Timeframe.M1: "TIMEFRAME_M1",
            Timeframe.M5: "TIMEFRAME_M5",
            Timeframe.M15: "TIMEFRAME_M15",
        }
        attribute_name = mapping[timeframe]
        if not hasattr(module, attribute_name):
            raise MT5IntegrationError("timeframe_not_supported", {"timeframe": timeframe.value})
        return getattr(module, attribute_name)
