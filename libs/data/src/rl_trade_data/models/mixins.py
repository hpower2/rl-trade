"""Reusable SQLAlchemy mixins for persisted models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IntegerPrimaryKeyMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class SymbolForeignKeyMixin:
    symbol_id: Mapped[int] = mapped_column(
        sa.ForeignKey("symbols.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


Price = Decimal
