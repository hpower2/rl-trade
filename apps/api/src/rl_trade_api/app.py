"""FastAPI application bootstrap."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rl_trade_common import Settings, configure_logging, get_settings
from rl_trade_api.api.router import router as api_router
from rl_trade_api.core.errors import register_exception_handlers
from rl_trade_api.services.events import EventBroadcaster


def _build_cors_allow_origins(settings: Settings) -> list[str]:
    return sorted(
        {
            f"http://localhost:{settings.frontend_port}",
            f"http://127.0.0.1:{settings.frontend_port}",
            f"http://0.0.0.0:{settings.frontend_port}",
        }
    )


def _build_cors_allow_origin_regex() -> str:
    return (
        r"^https?://("
        r"localhost|"
        r"127\.0\.0\.1|"
        r"0\.0\.0\.0|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r")(?::\d+)?$"
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(service_name="api", settings=settings)

    app = FastAPI(
        title="Forex Trainer & Paper Trading Dashboard API",
        version="0.1.0",
        summary="Bootstrap API surface for the rl-trade monorepo.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_build_cors_allow_origins(settings),
        allow_origin_regex=_build_cors_allow_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )
    app.state.settings = settings
    app.state.event_broadcaster = EventBroadcaster()
    register_exception_handlers(app)
    app.include_router(api_router)

    return app
