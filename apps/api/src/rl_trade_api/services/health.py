"""Health probe implementations for API endpoints."""

from __future__ import annotations

from importlib import util as importlib_util
from typing import Any

from redis import Redis
from sqlalchemy import Engine, text

from rl_trade_common import Settings
from rl_trade_api.schemas.system import ComponentHealthResponse, SystemStatusResponse


def check_database_health(engine: Engine) -> ComponentHealthResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        return ComponentHealthResponse(
            name="db",
            status="unavailable",
            details={"dialect": engine.dialect.name, "reason": str(exc)},
        )

    return ComponentHealthResponse(
        name="db",
        status="ok",
        details={"dialect": engine.dialect.name},
    )


def check_redis_health(client: Redis) -> ComponentHealthResponse:
    try:
        client.ping()
    except Exception as exc:
        return ComponentHealthResponse(
            name="redis",
            status="unavailable",
            details={"reason": str(exc)},
        )

    return ComponentHealthResponse(name="redis", status="ok")


def check_gpu_health() -> ComponentHealthResponse:
    if importlib_util.find_spec("torch") is None:
        return ComponentHealthResponse(
            name="gpu",
            status="unavailable",
            details={"reason": "torch_not_installed"},
        )

    import torch

    if not torch.cuda.is_available():
        return ComponentHealthResponse(
            name="gpu",
            status="unavailable",
            details={"reason": "cuda_unavailable"},
        )

    return ComponentHealthResponse(
        name="gpu",
        status="ok",
        details={
            "device_count": torch.cuda.device_count(),
            "device_names": [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())],
        },
    )


def collect_system_health(
    *,
    settings: Settings,
    engine: Engine,
    redis_client: Redis,
) -> dict[str, ComponentHealthResponse]:
    return {
        "api": ComponentHealthResponse(
            name="api",
            status="ok",
            details={"environment": settings.app_env},
        ),
        "db": check_database_health(engine),
        "redis": check_redis_health(redis_client),
        "gpu": check_gpu_health(),
    }


def build_system_status(
    *,
    settings: Settings,
    components: dict[str, ComponentHealthResponse],
) -> SystemStatusResponse:
    overall_status = "ok" if all(component.status == "ok" for component in components.values()) else "degraded"
    return SystemStatusResponse(
        status=overall_status,
        environment=settings.app_env,
        paper_trading_only=settings.paper_trading_only,
        components=components,
    )
