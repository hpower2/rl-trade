"""Database engine and session lifecycle tests."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from rl_trade_data import build_engine, build_session_factory, session_scope


def test_session_scope_commits_successful_transactions(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'commit.sqlite'}"
    engine = build_engine(database_url)
    session_factory = build_session_factory(engine=engine)

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sample_rows (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"))

    with session_scope(session_factory) as session:
        session.execute(text("INSERT INTO sample_rows (value) VALUES (:value)"), {"value": "kept"})

    with engine.connect() as connection:
        stored_rows = connection.execute(text("SELECT value FROM sample_rows")).scalars().all()

    assert stored_rows == ["kept"]
    engine.dispose()


def test_session_scope_rolls_back_on_error(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'rollback.sqlite'}"
    engine = build_engine(database_url)
    session_factory = build_session_factory(engine=engine)

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sample_rows (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"))

    with pytest.raises(RuntimeError, match="force rollback"):
        with session_scope(session_factory) as session:
            session.execute(text("INSERT INTO sample_rows (value) VALUES (:value)"), {"value": "discarded"})
            raise RuntimeError("force rollback")

    with engine.connect() as connection:
        row_count = connection.execute(text("SELECT COUNT(*) FROM sample_rows")).scalar_one()

    assert row_count == 0
    engine.dispose()
