"""Model evaluation and approval endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_api_settings, get_db_session, get_event_broadcaster, require_authenticated_principal
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.evaluations import (
    ApprovedSymbolResponse,
    ModelEvaluationCreate,
    ModelEvaluationResponse,
    ModelEvaluationSummaryResponse,
    ModelRegistryEntryResponse,
)
from rl_trade_api.services import evaluations as evaluation_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common import Settings
from rl_trade_data.models import ModelStatus, ModelType

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post(
    "",
    response_model=ModelEvaluationResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_model_evaluation(
    payload: ModelEvaluationCreate,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    settings: Settings = Depends(get_api_settings),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> ModelEvaluationResponse:
    return evaluation_service.create_model_evaluation(
        session=session,
        settings=settings,
        principal=principal,
        payload=payload,
        event_broadcaster=event_broadcaster,
    )


@router.get(
    "/models",
    response_model=list[ModelRegistryEntryResponse],
)
def list_models(
    symbol_code: str | None = None,
    model_type: ModelType | None = None,
    status: ModelStatus | None = None,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> list[ModelRegistryEntryResponse]:
    del principal
    return evaluation_service.list_models(
        session=session,
        symbol_code=symbol_code,
        model_type=model_type,
        status=status,
    )


@router.get(
    "/reports",
    response_model=list[ModelEvaluationSummaryResponse],
)
def list_evaluation_reports(
    symbol_code: str | None = None,
    model_type: ModelType | None = None,
    model_id: int | None = None,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> list[ModelEvaluationSummaryResponse]:
    del principal
    return evaluation_service.list_evaluation_reports(
        session=session,
        symbol_code=symbol_code,
        model_type=model_type,
        model_id=model_id,
    )


@router.get(
    "/approved-symbols",
    response_model=list[ApprovedSymbolResponse],
)
def list_approved_symbols(
    symbol_code: str | None = None,
    model_type: ModelType | None = None,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> list[ApprovedSymbolResponse]:
    del principal
    return evaluation_service.list_approved_symbols(
        session=session,
        symbol_code=symbol_code,
        model_type=model_type,
    )
