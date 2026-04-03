"""System status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import Engine

from rl_trade_common import Settings
from rl_trade_api.api.deps import get_api_settings, get_db_engine, get_redis_client
from rl_trade_api.schemas.system import SystemStatusResponse
from rl_trade_api.services import health as health_service

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
def read_system_status(
    settings: Settings = Depends(get_api_settings),
    engine: Engine = Depends(get_db_engine),
    client: Redis = Depends(get_redis_client),
) -> SystemStatusResponse:
    components = health_service.collect_system_health(
        settings=settings,
        engine=engine,
        redis_client=client,
    )
    return health_service.build_system_status(settings=settings, components=components)
