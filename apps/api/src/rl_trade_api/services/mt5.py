"""MT5-facing API service helpers."""

from __future__ import annotations

from fastapi import HTTPException, status

from rl_trade_api.schemas.mt5 import MT5ConnectionStatusResponse, MT5SymbolResponse, MT5SymbolsResponse
from rl_trade_common import Settings
from rl_trade_trading import MT5ConnectionState, MT5Gateway, MT5IntegrationError


def get_connection_status(*, gateway: MT5Gateway, settings: Settings) -> MT5ConnectionStatusResponse:
    state = gateway.get_connection_state(settings)
    return MT5ConnectionStatusResponse(
        status=state.status,
        account_login=state.account_login,
        server_name=state.server_name,
        account_name=state.account_name,
        account_currency=state.account_currency,
        leverage=state.leverage,
        is_demo=state.is_demo,
        trade_allowed=state.trade_allowed,
        paper_trading_allowed=state.paper_trading_allowed,
        reason=state.reason,
        details=state.details,
    )


def list_symbols(
    *,
    gateway: MT5Gateway,
    settings: Settings,
    query: str | None = None,
) -> MT5SymbolsResponse:
    try:
        symbols = gateway.list_symbols(settings, query=query)
    except MT5IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MT5 symbol listing unavailable: {exc.reason}.",
        ) from exc

    return MT5SymbolsResponse(
        count=len(symbols),
        symbols=[
            MT5SymbolResponse(
                code=symbol.code,
                description=symbol.description,
                path=symbol.path,
                visible=symbol.visible,
                spread=symbol.spread,
            )
            for symbol in symbols
        ],
    )
