"""MT5 API response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from rl_trade_data.models.enums import ConnectionStatus


class MT5ConnectionStatusResponse(BaseModel):
    status: ConnectionStatus
    account_login: int | None = None
    server_name: str | None = None
    account_name: str | None = None
    account_currency: str | None = None
    leverage: int | None = None
    is_demo: bool | None = None
    trade_allowed: bool | None = None
    paper_trading_allowed: bool
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class MT5SymbolResponse(BaseModel):
    code: str
    description: str | None = None
    path: str | None = None
    visible: bool | None = None
    spread: int | None = None


class MT5SymbolsResponse(BaseModel):
    count: int
    symbols: list[MT5SymbolResponse] = Field(default_factory=list)
