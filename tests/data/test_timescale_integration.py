"""PostgreSQL + TimescaleDB migration validation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.mark.skipif(
    "RL_TRADE_TEST_POSTGRES_URL" not in os.environ,
    reason="RL_TRADE_TEST_POSTGRES_URL is required for Timescale integration tests.",
)
def test_timescale_upgrade_inspection_and_reupgrade() -> None:
    database_url = os.environ["RL_TRADE_TEST_POSTGRES_URL"]
    config = build_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == "0003_enable_ohlc_hypertable"

        extension_name = connection.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
        ).scalar_one()
        assert extension_name == "timescaledb"

        hypertable_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public'
                  AND hypertable_name = 'ohlc_candles'
                """
            )
        ).scalar_one()
        assert hypertable_count == 1

        index_names = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'ohlc_candles'
                    """
                )
            )
        }
        assert {
            "ix_ohlc_candles_candle_time",
            "ix_ohlc_candles_symbol_id",
            "ix_ohlc_candles_symbol_timeframe_time",
            "pk_ohlc_candles",
        }.issubset(index_names)

    engine.dispose()

    command.downgrade(config, "base")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        remaining_versions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        assert remaining_versions == []

        extension_count = connection.execute(
            text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'")
        ).scalar_one()
        assert extension_count == 0

    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        hypertable_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public'
                  AND hypertable_name = 'ohlc_candles'
                """
            )
        ).scalar_one()
        assert hypertable_count == 1
    engine.dispose()
