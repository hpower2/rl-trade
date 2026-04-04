"""Ingestion request endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_db_session, get_event_broadcaster, require_authenticated_principal
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.ingestion import IngestionJobResponse, IngestionRequest
from rl_trade_api.services import ingestion as ingestion_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post(
    "/request",
    response_model=IngestionJobResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def request_ingestion(
    payload: IngestionRequest,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> IngestionJobResponse:
    return ingestion_service.request_ingestion(
        session=session,
        principal=principal,
        payload=payload,
        event_broadcaster=event_broadcaster,
    )


@router.post(
    "/{job_id}/retry",
    response_model=IngestionJobResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def retry_ingestion(
    job_id: int,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> IngestionJobResponse:
    return ingestion_service.retry_ingestion(
        session=session,
        principal=principal,
        job_id=job_id,
        event_broadcaster=event_broadcaster,
    )
