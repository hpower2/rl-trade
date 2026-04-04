"""Top-level API router composition."""

from fastapi import APIRouter

from rl_trade_api.api.routes.events import router as events_router
from rl_trade_api.api.routes.health import router as health_router
from rl_trade_api.api.v1.router import router as v1_router

router = APIRouter()
router.include_router(events_router)
router.include_router(health_router)
router.include_router(v1_router)
