"""Versioned API router."""

from fastapi import APIRouter

from rl_trade_api.api.v1.routes.auth import router as auth_router
from rl_trade_api.api.v1.routes.evaluations import router as evaluations_router
from rl_trade_api.api.v1.routes.ingestion import router as ingestion_router
from rl_trade_api.api.v1.routes.jobs import router as jobs_router
from rl_trade_api.api.v1.routes.mt5 import router as mt5_router
from rl_trade_api.api.v1.routes.preprocessing import router as preprocessing_router
from rl_trade_api.api.v1.routes.symbols import router as symbols_router
from rl_trade_api.api.v1.routes.system import router as system_router
from rl_trade_api.api.v1.routes.training import router as training_router
from rl_trade_api.api.v1.routes.trading import router as trading_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(evaluations_router)
router.include_router(ingestion_router)
router.include_router(jobs_router)
router.include_router(mt5_router)
router.include_router(preprocessing_router)
router.include_router(symbols_router)
router.include_router(system_router)
router.include_router(training_router)
router.include_router(trading_router)
