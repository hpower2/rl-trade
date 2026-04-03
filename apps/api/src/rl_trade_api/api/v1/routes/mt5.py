"""MT5 connectivity endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from rl_trade_api.api.deps import get_api_settings, get_mt5_gateway, require_authenticated_principal
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.mt5 import MT5ConnectionStatusResponse, MT5SymbolsResponse
from rl_trade_api.services import mt5 as mt5_service
from rl_trade_common import Settings
from rl_trade_trading import MT5Gateway

router = APIRouter(prefix="/mt5", tags=["mt5"])


@router.get("/status", response_model=MT5ConnectionStatusResponse)
def read_mt5_status(
    _: object = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
) -> MT5ConnectionStatusResponse:
    return mt5_service.get_connection_status(gateway=gateway, settings=settings)


@router.get(
    "/symbols",
    response_model=MT5SymbolsResponse,
    responses={503: {"model": ErrorResponse}},
)
def read_mt5_symbols(
    _: object = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    query: str | None = Query(default=None, min_length=1, max_length=32),
) -> MT5SymbolsResponse:
    return mt5_service.list_symbols(gateway=gateway, settings=settings, query=query)
