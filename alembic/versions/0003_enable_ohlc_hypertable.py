"""Convert ohlc_candles into a TimescaleDB hypertable on PostgreSQL."""

from __future__ import annotations

from alembic import op

revision = "0003_enable_ohlc_hypertable"
down_revision = "0002_create_application_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        SELECT create_hypertable(
            'ohlc_candles',
            by_range('candle_time'),
            if_not_exists => TRUE,
            migrate_data => TRUE,
            create_default_indexes => FALSE
        )
        """
    )


def downgrade() -> None:
    # Downgrading to base is handled by the schema-drop migration. There is no
    # lightweight table-preserving downgrade requirement for this milestone.
    return
