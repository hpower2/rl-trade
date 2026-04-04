"""Paper-trading signal endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import (
    get_api_settings,
    get_db_session,
    get_event_broadcaster,
    get_mt5_gateway,
    require_authenticated_principal,
)
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.trading import (
    PaperTradeOrderCreate,
    PaperTradeOrderListResponse,
    PaperTradeOrderResponse,
    PaperTradingSyncResponse,
    PaperTradingStatusResponse,
    PaperTradePositionCloseResponse,
    PaperTradePositionListResponse,
    PaperTradeSignalCreate,
    PaperTradeSignalListResponse,
    PaperTradeSignalResponse,
)
from rl_trade_api.services import trading as trading_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common import Settings
from rl_trade_data.models import OrderStatus, PositionStatus, SignalStatus
from rl_trade_trading import MT5Gateway

router = APIRouter(prefix="/trading", tags=["trading"])


@router.get(
    "/status",
    response_model=PaperTradingStatusResponse,
)
def read_paper_trading_status(
    _: object = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    session: Session = Depends(get_db_session),
) -> PaperTradingStatusResponse:
    return trading_service.get_trading_status(
        session=session,
        settings=settings,
        gateway=gateway,
    )


@router.post(
    "/start",
    response_model=PaperTradingStatusResponse,
    responses={409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def start_paper_trading(
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> PaperTradingStatusResponse:
    return trading_service.start_trading(
        session=session,
        settings=settings,
        principal=principal,
        gateway=gateway,
        event_broadcaster=event_broadcaster,
    )


@router.post(
    "/stop",
    response_model=PaperTradingStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
def stop_paper_trading(
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    session: Session = Depends(get_db_session),
) -> PaperTradingStatusResponse:
    return trading_service.stop_trading(
        session=session,
        settings=settings,
        principal=principal,
        gateway=gateway,
    )


@router.post(
    "/sync",
    response_model=PaperTradingSyncResponse,
    responses={409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def sync_paper_trading_state(
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> PaperTradingSyncResponse:
    return trading_service.sync_trading_state(
        session=session,
        settings=settings,
        principal=principal,
        gateway=gateway,
        event_broadcaster=event_broadcaster,
    )


@router.post(
    "/signals",
    response_model=PaperTradeSignalResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_paper_trade_signal(
    payload: PaperTradeSignalCreate,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> PaperTradeSignalResponse:
    return trading_service.create_signal(
        session=session,
        settings=settings,
        principal=principal,
        gateway=gateway,
        payload=payload,
        event_broadcaster=event_broadcaster,
    )


@router.get(
    "/signals",
    response_model=PaperTradeSignalListResponse,
    responses={404: {"model": ErrorResponse}},
)
def list_paper_trade_signals(
    symbol_code: str | None = Query(default=None, min_length=1, max_length=32),
    status_filter: SignalStatus | None = Query(default=None, alias="status"),
    _: object = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> PaperTradeSignalListResponse:
    return trading_service.list_signals(
        session=session,
        symbol_code=symbol_code,
        status_filter=status_filter,
    )


@router.post(
    "/orders",
    response_model=PaperTradeOrderResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_paper_trade_order(
    payload: PaperTradeOrderCreate,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> PaperTradeOrderResponse:
    return trading_service.create_order(
        session=session,
        settings=settings,
        principal=principal,
        gateway=gateway,
        payload=payload,
        event_broadcaster=event_broadcaster,
    )


@router.get(
    "/orders",
    response_model=PaperTradeOrderListResponse,
    responses={404: {"model": ErrorResponse}},
)
def list_paper_trade_orders(
    symbol_code: str | None = Query(default=None, min_length=1, max_length=32),
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    _: object = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> PaperTradeOrderListResponse:
    return trading_service.list_orders(
        session=session,
        symbol_code=symbol_code,
        status_filter=status_filter,
    )


@router.get(
    "/positions",
    response_model=PaperTradePositionListResponse,
    responses={404: {"model": ErrorResponse}},
)
def list_paper_trade_positions(
    symbol_code: str | None = Query(default=None, min_length=1, max_length=32),
    status_filter: PositionStatus | None = Query(default=None, alias="status"),
    _: object = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> PaperTradePositionListResponse:
    return trading_service.list_positions(
        session=session,
        symbol_code=symbol_code,
        status_filter=status_filter,
    )


@router.post(
    "/positions/{position_id}/close",
    response_model=PaperTradePositionCloseResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def close_paper_trade_position(
    position_id: int,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    gateway: MT5Gateway = Depends(get_mt5_gateway),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> PaperTradePositionCloseResponse:
    return trading_service.close_position(
        session=session,
        settings=settings,
        principal=principal,
        gateway=gateway,
        position_id=position_id,
        event_broadcaster=event_broadcaster,
    )
