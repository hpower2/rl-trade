"""Public health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import Engine

from rl_trade_common import Settings
from rl_trade_api.api.deps import get_api_settings, get_db_engine, get_redis_client
from rl_trade_api.schemas.system import APIInfoResponse, ComponentHealthResponse
from rl_trade_api.services import health as health_service

router = APIRouter(tags=["health"])


@router.get("/", response_model=APIInfoResponse, tags=["system"])
def read_root(settings: Settings = Depends(get_api_settings)) -> APIInfoResponse:
    return APIInfoResponse(
        service="api",
        status="bootstrapped",
        environment=settings.app_env,
        paper_trading_only=settings.paper_trading_only,
    )


@router.get("/health", response_model=APIInfoResponse)
def read_health(settings: Settings = Depends(get_api_settings)) -> APIInfoResponse:
    return APIInfoResponse(
        service="api",
        status="ok",
        environment=settings.app_env,
        paper_trading_only=settings.paper_trading_only,
    )


@router.get(
    "/health/db",
    response_model=ComponentHealthResponse,
    responses={503: {"model": ComponentHealthResponse}},
)
def read_database_health(engine: Engine = Depends(get_db_engine)) -> ComponentHealthResponse | JSONResponse:
    component = health_service.check_database_health(engine)
    if component.status != "ok":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=component.model_dump())
    return component


@router.get(
    "/health/redis",
    response_model=ComponentHealthResponse,
    responses={503: {"model": ComponentHealthResponse}},
)
def read_redis_health(client: Redis = Depends(get_redis_client)) -> ComponentHealthResponse | JSONResponse:
    component = health_service.check_redis_health(client)
    if component.status != "ok":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=component.model_dump())
    return component


@router.get(
    "/health/gpu",
    response_model=ComponentHealthResponse,
    responses={503: {"model": ComponentHealthResponse}},
)
def read_gpu_health() -> ComponentHealthResponse | JSONResponse:
    component = health_service.check_gpu_health()
    if component.status != "ok":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=component.model_dump())
    return component
