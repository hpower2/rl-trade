"""Dependency injection helpers for API handlers."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import Redis
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from rl_trade_common import Settings, get_settings
from rl_trade_api.services import auth as auth_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_data import get_engine, get_session_factory
from rl_trade_trading import MT5Gateway

http_bearer = HTTPBearer(auto_error=False)


def get_api_settings() -> Settings:
    return get_settings()


def get_db_engine() -> Engine:
    return get_engine()


def get_db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    settings = get_api_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


@lru_cache(maxsize=1)
def get_mt5_gateway() -> MT5Gateway:
    return MT5Gateway()


def get_event_broadcaster(request: Request) -> EventBroadcaster:
    return request.app.state.event_broadcaster


def get_optional_principal(
    settings: Settings = Depends(get_api_settings),
    credentials: HTTPAuthorizationCredentials | None = Security(http_bearer),
) -> AuthPrincipal | None:
    return auth_service.resolve_principal(settings=settings, credentials=credentials)


def require_authenticated_principal(
    principal: AuthPrincipal | None = Depends(get_optional_principal),
) -> AuthPrincipal:
    if principal is None:
        raise auth_service.authentication_required_error()
    return principal
