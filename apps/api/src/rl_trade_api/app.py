"""FastAPI application bootstrap."""

from fastapi import FastAPI

from rl_trade_common import configure_logging, get_settings
from rl_trade_api.api.router import router as api_router
from rl_trade_api.core.errors import register_exception_handlers
from rl_trade_api.services.events import EventBroadcaster


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(service_name="api", settings=settings)

    app = FastAPI(
        title="Forex Trainer & Paper Trading Dashboard API",
        version="0.1.0",
        summary="Bootstrap API surface for the rl-trade monorepo.",
    )
    app.state.settings = settings
    app.state.event_broadcaster = EventBroadcaster()
    register_exception_handlers(app)
    app.include_router(api_router)

    return app
