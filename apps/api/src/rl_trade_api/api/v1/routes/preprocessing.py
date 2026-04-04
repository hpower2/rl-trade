"""Preprocessing request endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_db_session, get_event_broadcaster, require_authenticated_principal
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.preprocessing import PreprocessingJobResponse, PreprocessingRequest
from rl_trade_api.services import preprocessing as preprocessing_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster

router = APIRouter(prefix="/preprocessing", tags=["preprocessing"])


@router.post(
    "/request",
    response_model=PreprocessingJobResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def request_preprocessing(
    payload: PreprocessingRequest,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> PreprocessingJobResponse:
    return preprocessing_service.request_preprocessing(
        session=session,
        principal=principal,
        payload=payload,
        event_broadcaster=event_broadcaster,
    )
