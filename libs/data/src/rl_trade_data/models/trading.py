"""Persistence models for trading, audit, and platform logs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from rl_trade_data.db.base import Base
from rl_trade_data.models.enums import AuditOutcome, OrderStatus, OrderType, PositionStatus, SignalStatus, SystemLogLevel, Timeframe, TradeSide
from rl_trade_data.models.mixins import CreatedAtMixin, IntegerPrimaryKeyMixin, SymbolForeignKeyMixin, TimestampMixin


class PaperTradeSignal(IntegerPrimaryKeyMixin, CreatedAtMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "paper_trade_signals"
    __table_args__ = (
        sa.Index("ix_paper_trade_signals_signal_time", "signal_time"),
        sa.Index("ix_paper_trade_signals_status_created_at", "status", "created_at"),
    )

    approved_model_id: Mapped[int] = mapped_column(
        sa.ForeignKey("approved_models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[Timeframe] = mapped_column(
        sa.Enum(Timeframe, name="timeframe_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    side: Mapped[TradeSide] = mapped_column(
        sa.Enum(TradeSide, name="trade_side_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    status: Mapped[SignalStatus] = mapped_column(
        sa.Enum(SignalStatus, name="signal_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=SignalStatus.PENDING,
        server_default=SignalStatus.PENDING.value,
    )
    signal_time: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    take_profit: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    rationale: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class PaperTradeOrder(IntegerPrimaryKeyMixin, TimestampMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "paper_trade_orders"
    __table_args__ = (
        sa.UniqueConstraint("broker_order_id", name="uq_paper_trade_orders_broker_order_id"),
        sa.Index("ix_paper_trade_orders_status_created_at", "status", "created_at"),
    )

    signal_id: Mapped[int] = mapped_column(
        sa.ForeignKey("paper_trade_signals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mt5_account_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("mt5_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    side: Mapped[TradeSide] = mapped_column(
        sa.Enum(TradeSide, name="trade_side_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    order_type: Mapped[OrderType] = mapped_column(
        sa.Enum(OrderType, name="order_type_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=OrderType.MARKET,
        server_default=OrderType.MARKET.value,
    )
    status: Mapped[OrderStatus] = mapped_column(
        sa.Enum(OrderStatus, name="order_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=OrderStatus.PENDING,
        server_default=OrderStatus.PENDING.value,
    )
    broker_order_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    requested_quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    filled_quantity: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    requested_price: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    filled_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)


class PaperTradePosition(IntegerPrimaryKeyMixin, TimestampMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "paper_trade_positions"
    __table_args__ = (
        sa.UniqueConstraint("order_id", name="uq_paper_trade_positions_order_id"),
        sa.Index("ix_paper_trade_positions_status_created_at", "status", "created_at"),
    )

    order_id: Mapped[int] = mapped_column(
        sa.ForeignKey("paper_trade_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    side: Mapped[TradeSide] = mapped_column(
        sa.Enum(TradeSide, name="trade_side_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    status: Mapped[PositionStatus] = mapped_column(
        sa.Enum(PositionStatus, name="position_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=PositionStatus.OPEN,
        server_default=PositionStatus.OPEN.value,
    )
    opened_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    close_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)


class TradeExecution(IntegerPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "trade_executions"
    __table_args__ = (
        sa.Index("ix_trade_executions_execution_time", "execution_time"),
    )

    order_id: Mapped[int] = mapped_column(
        sa.ForeignKey("paper_trade_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("paper_trade_positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    execution_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    execution_time: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    price: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    commission: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    slippage: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    raw_execution: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class EquitySnapshot(IntegerPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "equity_snapshots"
    __table_args__ = (
        sa.UniqueConstraint("mt5_account_id", "snapshot_time", name="uq_equity_snapshots_account_snapshot_time"),
        sa.Index("ix_equity_snapshots_snapshot_time", "snapshot_time"),
    )

    mt5_account_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("mt5_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_time: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    balance: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    equity: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    margin: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    free_margin: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 8), nullable=True)
    open_positions_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class AuditLog(IntegerPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        sa.Index("ix_audit_logs_entity_lookup", "entity_type", "entity_id", "created_at"),
    )

    action: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    actor_type: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    entity_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    outcome: Mapped[AuditOutcome] = mapped_column(
        sa.Enum(AuditOutcome, name="audit_outcome_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class SystemLog(IntegerPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "system_logs"
    __table_args__ = (
        sa.Index("ix_system_logs_service_level_created_at", "service", "level", "created_at"),
    )

    service: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    level: Mapped[SystemLogLevel] = mapped_column(
        sa.Enum(SystemLogLevel, name="system_log_level_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    event: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    message: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    context: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
