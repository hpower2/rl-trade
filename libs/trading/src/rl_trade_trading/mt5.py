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
    balance: Decimal | None = None
    equity: Decimal | None = None
    margin: Decimal | None = None
    free_margin: Decimal | None = None
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


@dataclass(frozen=True, slots=True)
class MT5OrderResult:
    accepted: bool
    filled: bool
    broker_order_id: str | None
    execution_price: Decimal | None
    execution_quantity: Decimal | None
    execution_time: datetime | None
    rejection_reason: str | None = None
    comment: str | None = None
    raw_result: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MT5HistoricalOrderRecord:
    broker_order_id: str | None
    status: str
    execution_price: Decimal | None
    execution_quantity: Decimal | None
    execution_time: datetime | None
    rejection_reason: str | None = None
    comment: str | None = None
    raw_record: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MT5PositionRecord:
    broker_order_id: str | None
    symbol_code: str
    side: str | None
    quantity: Decimal
    open_price: Decimal
    current_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    opened_at: datetime | None
    unrealized_pnl: Decimal | None = None
    comment: str | None = None
    raw_record: dict[str, Any] = field(default_factory=dict)


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

    def submit_paper_order(
        self,
        settings: Settings,
        *,
        symbol_code: str,
        side: str,
        quantity: Decimal | float | int | str,
        price: Decimal | float | int | str,
        stop_loss: Decimal | float | int | str,
        take_profit: Decimal | float | int | str,
        comment: str | None = None,
    ) -> MT5OrderResult:
        with self._connected_module(settings) as module:
            order_send = getattr(module, "order_send", None)
            if not callable(order_send):
                raise MT5IntegrationError("order_send_unavailable")

            order_type = self._resolve_order_type(module, side)
            request = {
                "action": getattr(module, "TRADE_ACTION_DEAL", None),
                "symbol": symbol_code,
                "volume": float(Decimal(str(quantity))),
                "type": order_type,
                "price": float(Decimal(str(price))),
                "sl": float(Decimal(str(stop_loss))),
                "tp": float(Decimal(str(take_profit))),
                "comment": comment or "rl_trade_paper",
            }
            type_time = getattr(module, "ORDER_TIME_GTC", None)
            if type_time is not None:
                request["type_time"] = type_time
            type_filling = getattr(module, "ORDER_FILLING_IOC", None)
            if type_filling is not None:
                request["type_filling"] = type_filling

            result = order_send(request)
            if result is None:
                raise MT5IntegrationError("order_send_failed", self._last_error_details(module))

            return self._build_order_result(module, result)

    def list_open_positions(self, settings: Settings) -> list[MT5PositionRecord]:
        with self._connected_module(settings) as module:
            positions_get = getattr(module, "positions_get", None)
            if not callable(positions_get):
                raise MT5IntegrationError("positions_get_unavailable")

            positions = positions_get()
            if positions is None:
                raise MT5IntegrationError("positions_unavailable", self._last_error_details(module))

            return [self._build_position_record(module, position) for position in positions]

    def list_order_history(
        self,
        settings: Settings,
        *,
        start_time: datetime,
        end_time: datetime | None = None,
    ) -> list[MT5HistoricalOrderRecord]:
        with self._connected_module(settings) as module:
            history_orders_get = getattr(module, "history_orders_get", None)
            if not callable(history_orders_get):
                raise MT5IntegrationError("history_orders_get_unavailable")

            history = history_orders_get(start_time, end_time or datetime.now(timezone.utc))
            if history is None:
                raise MT5IntegrationError("history_orders_unavailable", self._last_error_details(module))

            return [self._build_historical_order_record(module, record) for record in history]

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
            balance=self._normalize_decimal_attr(account, "balance"),
            equity=self._normalize_decimal_attr(account, "equity"),
            margin=self._normalize_decimal_attr(account, "margin"),
            free_margin=self._first_decimal(account, "margin_free", "free_margin"),
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

    def _build_order_result(self, module: Any, result: Any) -> MT5OrderResult:
        retcode = self._get_attr(result, "retcode")
        done_retcode = getattr(module, "TRADE_RETCODE_DONE", None)
        placed_retcode = getattr(module, "TRADE_RETCODE_PLACED", None)
        partial_retcode = getattr(module, "TRADE_RETCODE_DONE_PARTIAL", None)
        success_codes = {code for code in (done_retcode, placed_retcode, partial_retcode) if code is not None}

        broker_order_id = self._resolve_broker_order_id(result)
        execution_price = self._normalize_decimal_attr(result, "price")
        execution_quantity = self._normalize_decimal_attr(result, "volume")
        execution_time = datetime.now(timezone.utc)
        comment = self._get_attr(result, "comment")
        raw_result = self._result_to_dict(result)

        if retcode in success_codes:
            return MT5OrderResult(
                accepted=True,
                filled=retcode in {done_retcode, partial_retcode},
                broker_order_id=broker_order_id,
                execution_price=execution_price,
                execution_quantity=execution_quantity,
                execution_time=execution_time,
                comment=comment,
                raw_result=raw_result,
            )

        rejection_reason = str(comment or self._last_error_details(module).get("message") or "order_rejected")
        return MT5OrderResult(
            accepted=False,
            filled=False,
            broker_order_id=broker_order_id,
            execution_price=execution_price,
            execution_quantity=execution_quantity,
            execution_time=execution_time,
            rejection_reason=rejection_reason,
            comment=comment,
            raw_result=raw_result,
        )

    def _build_historical_order_record(self, module: Any, record: Any) -> MT5HistoricalOrderRecord:
        state = self._get_attr(record, "state")
        filled_state = getattr(module, "ORDER_STATE_FILLED", None)
        cancelled_state = getattr(module, "ORDER_STATE_CANCELED", getattr(module, "ORDER_STATE_CANCELLED", None))
        rejected_state = getattr(module, "ORDER_STATE_REJECTED", None)

        status = "submitted"
        if state == filled_state:
            status = "filled"
        elif state == cancelled_state:
            status = "cancelled"
        elif state == rejected_state:
            status = "rejected"

        return MT5HistoricalOrderRecord(
            broker_order_id=self._resolve_broker_order_id(record),
            status=status,
            execution_price=self._first_decimal(record, "price_current", "price_open", "price"),
            execution_quantity=self._first_decimal(record, "volume_current", "volume_initial", "volume"),
            execution_time=self._first_datetime(record, "time_done_msc", "time_done", "time_setup_msc", "time_setup"),
            rejection_reason=(
                str(self._get_attr(record, "comment") or self._get_attr(record, "reason"))
                if status in {"rejected", "cancelled"}
                else None
            ),
            comment=self._coerce_optional_str(self._get_attr(record, "comment")),
            raw_record=self._result_to_dict(record),
        )

    def _build_position_record(self, module: Any, position: Any) -> MT5PositionRecord:
        position_type = self._get_attr(position, "type")
        side: str | None
        if position_type == getattr(module, "POSITION_TYPE_BUY", None):
            side = "long"
        elif position_type == getattr(module, "POSITION_TYPE_SELL", None):
            side = "short"
        else:
            side = self._coerce_optional_str(position_type)

        symbol_code = self._coerce_optional_str(self._get_attr(position, "symbol")) or ""
        return MT5PositionRecord(
            broker_order_id=self._resolve_broker_order_id(position),
            symbol_code=symbol_code,
            side=side,
            quantity=self._first_decimal(position, "volume") or Decimal("0"),
            open_price=self._first_decimal(position, "price_open", "price") or Decimal("0"),
            current_price=self._first_decimal(position, "price_current"),
            stop_loss=self._first_decimal(position, "sl"),
            take_profit=self._first_decimal(position, "tp"),
            opened_at=self._first_datetime(position, "time_msc", "time"),
            unrealized_pnl=self._first_decimal(position, "profit"),
            comment=self._coerce_optional_str(self._get_attr(position, "comment")),
            raw_record=self._result_to_dict(position),
        )

    def _last_error_details(self, module: Any) -> dict[str, Any]:
        error = getattr(module, "last_error", lambda: None)()
        if isinstance(error, tuple) and len(error) == 2:
            return {"code": error[0], "message": error[1]}
        return {"message": str(error) if error is not None else "unknown"}

    def _resolve_order_type(self, module: Any, side: str) -> Any:
        side_normalized = str(side).lower()
        if side_normalized == "long":
            return getattr(module, "ORDER_TYPE_BUY", 0)
        if side_normalized == "short":
            return getattr(module, "ORDER_TYPE_SELL", 1)
        raise MT5IntegrationError("unsupported_trade_side", {"side": side})

    def _resolve_broker_order_id(self, result: Any) -> str | None:
        for field_name in ("order", "deal", "ticket", "identifier"):
            value = self._get_attr(result, field_name)
            if value not in (None, 0, "0", ""):
                return str(value)
        return None

    def _normalize_decimal_attr(self, result: Any, field_name: str) -> Decimal | None:
        value = self._get_attr(result, field_name)
        if value in (None, ""):
            return None
        return Decimal(str(value))

    def _first_decimal(self, result: Any, *field_names: str) -> Decimal | None:
        for field_name in field_names:
            value = self._get_attr(result, field_name)
            if value not in (None, ""):
                return Decimal(str(value))
        return None

    def _first_datetime(self, result: Any, *field_names: str) -> datetime | None:
        for field_name in field_names:
            value = self._get_attr(result, field_name)
            parsed = self._coerce_datetime_value(value)
            if parsed is not None:
                return parsed
        return None

    def _coerce_datetime_value(self, value: Any) -> datetime | None:
        if value in (None, "", 0):
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return None
        if numeric_value > 1_000_000_000_000:
            numeric_value /= 1000
        return datetime.fromtimestamp(numeric_value, tz=timezone.utc)

    def _coerce_optional_str(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)

    def _result_to_dict(self, result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return dict(result)
        if hasattr(result, "_asdict"):
            try:
                return dict(result._asdict())
            except Exception:
                return {}
        return {
            field_name: getattr(result, field_name)
            for field_name in ("retcode", "order", "deal", "price", "volume", "comment")
            if hasattr(result, field_name)
        }

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
