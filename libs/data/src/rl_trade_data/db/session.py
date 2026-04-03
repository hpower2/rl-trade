"""Engine and session factory helpers for the shared data layer."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from rl_trade_common import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    return create_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return build_engine()


def build_session_factory(
    *,
    database_url: str | None = None,
    engine: Engine | None = None,
) -> sessionmaker[Session]:
    active_engine = engine or build_engine(database_url)
    return sessionmaker(
        bind=active_engine,
        autoflush=False,
        expire_on_commit=False,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return build_session_factory(engine=get_engine())


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] | None = None,
) -> Iterator[Session]:
    factory = session_factory or get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
