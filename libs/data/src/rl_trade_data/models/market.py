"""Market and account-oriented persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from rl_trade_data.db.base import Base
from rl_trade_data.models.enums import ConnectionStatus, Timeframe
from rl_trade_data.models.mixins import CreatedAtMixin, IntegerPrimaryKeyMixin, TimestampMixin


class Symbol(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "symbols"
    __table_args__ = (
        sa.UniqueConstraint("code", name="uq_symbols_code"),
        sa.Index("ix_symbols_provider_code", "provider", "code"),
    )

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    base_currency: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    quote_currency: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="mt5")
    asset_class: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="forex")
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True, server_default=sa.true())


class SymbolValidationResult(IntegerPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "symbol_validation_results"
    __table_args__ = (
        sa.Index("ix_symbol_validation_results_requested_symbol", "requested_symbol", "validated_at"),
    )

    symbol_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("symbols.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_symbol: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    normalized_symbol: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="mt5")
    is_valid: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    validated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class OHLCCandle(CreatedAtMixin, Base):
    __tablename__ = "ohlc_candles"
    __table_args__ = (
        sa.CheckConstraint("high >= low", name="ck_ohlc_candles_high_gte_low"),
        sa.CheckConstraint("open >= low", name="ck_ohlc_candles_open_gte_low"),
        sa.CheckConstraint("close >= low", name="ck_ohlc_candles_close_gte_low"),
        sa.CheckConstraint("high >= open", name="ck_ohlc_candles_high_gte_open"),
        sa.CheckConstraint("high >= close", name="ck_ohlc_candles_high_gte_close"),
        sa.CheckConstraint("volume >= 0", name="ck_ohlc_candles_non_negative_volume"),
        sa.Index("ix_ohlc_candles_symbol_timeframe_time", "symbol_id", "timeframe", "candle_time"),
        sa.Index("ix_ohlc_candles_candle_time", "candle_time"),
    )

    symbol_id: Mapped[int] = mapped_column(
        sa.ForeignKey("symbols.id", ondelete="CASCADE"),
        primary_key=True,
    )
    timeframe: Mapped[Timeframe] = mapped_column(
        sa.Enum(Timeframe, name="timeframe_enum", native_enum=False, validate_strings=True),
        primary_key=True,
    )
    candle_time: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(sa.Numeric(18, 8), nullable=False, default=Decimal("0"))
    spread: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    provider: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="mt5")
    source: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="historical")
    ingested_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class MT5Account(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mt5_accounts"
    __table_args__ = (
        sa.UniqueConstraint("account_login", "server_name", name="uq_mt5_accounts_login_server"),
        sa.Index("ix_mt5_accounts_connection_status", "connection_status", "updated_at"),
    )

    account_login: Mapped[int] = mapped_column(sa.BigInteger(), nullable=False)
    server_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    account_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    account_currency: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    leverage: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    is_demo: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False, server_default=sa.false())
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        sa.Enum(ConnectionStatus, name="connection_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=ConnectionStatus.DISCONNECTED,
        server_default=ConnectionStatus.DISCONNECTED.value,
    )
    is_trade_allowed: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
