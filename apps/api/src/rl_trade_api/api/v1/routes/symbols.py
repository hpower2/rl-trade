"""Symbol validation endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_api_settings, get_db_session, get_mt5_gateway, require_authenticated_principal
from rl_trade_api.schemas.symbols import SymbolValidationRequest, SymbolValidationResponse
from rl_trade_api.services import symbols as symbols_service
from rl_trade_common import Settings
from rl_trade_trading import MT5Gateway

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.post("/validate", response_model=SymbolValidationResponse)
def validate_symbol(
    payload: SymbolValidationRequest,
    _: object = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
) -> SymbolValidationResponse:
    return symbols_service.validate_symbol(
        session=session,
        provider=gateway,
        settings=settings,
        requested_symbol=payload.symbol,
    )
