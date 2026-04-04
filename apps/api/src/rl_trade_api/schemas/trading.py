"""Schemas for paper-trading signal APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from rl_trade_data.models import ModelType, OrderStatus, PositionStatus, SignalStatus, Timeframe, TradeSide


class PaperTradeSignalCreate(BaseModel):
    symbol_code: str = Field(min_length=1, max_length=32)
    timeframe: Timeframe
    side: TradeSide
    confidence: float = Field(ge=0.0, le=100.0)
    entry_price: float = Field(gt=0.0)
    stop_loss: float = Field(gt=0.0)
    take_profit: float = Field(gt=0.0)
    signal_time: datetime | None = None
    model_type: ModelType | None = None
    rationale: dict[str, Any] = Field(default_factory=dict)


class PaperTradeSignalResponse(BaseModel):
    signal_id: int
    approved_model_id: int
    symbol_id: int
    symbol_code: str
    timeframe: Timeframe
    side: TradeSide
    status: SignalStatus
    signal_time: datetime
    confidence: float
    risk_to_reward: float
    entry_price: float
    stop_loss: float
    take_profit: float
    rationale: dict[str, Any] = Field(default_factory=dict)


class PaperTradeSignalListResponse(BaseModel):
    signals: list[PaperTradeSignalResponse] = Field(default_factory=list)


class PaperTradeOrderCreate(BaseModel):
    signal_id: int = Field(ge=1)
    quantity: float = Field(gt=0.0)


class PaperTradeOrderResponse(BaseModel):
    order_id: int
    signal_id: int
    symbol_id: int
    symbol_code: str
    side: TradeSide
    status: OrderStatus
    broker_order_id: str | None = None
    requested_quantity: float
    filled_quantity: float | None = None
    requested_price: float
    filled_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    rejection_reason: str | None = None


class PaperTradeOrderListResponse(BaseModel):
    orders: list[PaperTradeOrderResponse] = Field(default_factory=list)


class PaperTradePositionResponse(BaseModel):
    position_id: int
    order_id: int
    symbol_id: int
    symbol_code: str
    side: TradeSide
    status: PositionStatus
    opened_at: datetime
    closed_at: datetime | None = None
    quantity: float
    open_price: float
    close_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl: float | None = None


class PaperTradePositionListResponse(BaseModel):
    positions: list[PaperTradePositionResponse] = Field(default_factory=list)


class PaperTradePositionCloseResponse(BaseModel):
    position: PaperTradePositionResponse
    closing_order: PaperTradeOrderResponse


class PaperTradingSyncResponse(BaseModel):
    synced_at: datetime
    connection_status: str
    paper_trading_allowed: bool
    account_login: int | None = None
    orders_updated: int
    positions_updated: int
    executions_created: int
    history_records_seen: int
    broker_positions_seen: int


class PaperTradingStatusResponse(BaseModel):
    enabled: bool
    connection_status: str
    account_login: int | None = None
    server_name: str | None = None
    account_name: str | None = None
    is_demo: bool | None = None
    is_trade_allowed: bool | None = None
    paper_trading_allowed: bool
    reason: str | None = None
    approved_symbol_count: int
    accepted_signal_count: int
    open_order_count: int
    open_position_count: int
    last_started_at: datetime | None = None
    last_started_by: str | None = None
    last_stopped_at: datetime | None = None
    last_stopped_by: str | None = None
