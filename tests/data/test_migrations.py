"""Migration harness tests for the Alembic setup."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

import rl_trade_data.models  # noqa: F401
from rl_trade_data.db.base import metadata

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_and_downgrade_runs_cleanly(tmp_path) -> None:
    database_path = tmp_path / "migration.sqlite"
    database_url = f"sqlite+pysqlite:///{database_path}"
    config = build_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "0003_enable_ohlc_hypertable"
        actual_tables = set(inspect(connection).get_table_names())
        assert set(metadata.tables).issubset(actual_tables)

    command.downgrade(config, "base")

    with engine.connect() as connection:
        assert "alembic_version" in inspect(connection).get_table_names()
        remaining_versions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        assert remaining_versions == []

    engine.dispose()
