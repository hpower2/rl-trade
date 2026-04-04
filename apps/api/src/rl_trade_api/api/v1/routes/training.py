"""Training request intake endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_db_session, get_event_broadcaster, require_authenticated_principal
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.training import (
    SupervisedTrainingJobCreate,
    SupervisedTrainingJobResponse,
    SupervisedTrainingStatusResponse,
    TrainingRequestCreate,
    TrainingRequestResponse,
)
from rl_trade_api.services import training as training_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster

router = APIRouter(prefix="/training", tags=["training"])


@router.post(
    "/request",
    response_model=TrainingRequestResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def request_training(
    payload: TrainingRequestCreate,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> TrainingRequestResponse:
    return training_service.request_training(session=session, principal=principal, payload=payload)


@router.post(
    "/supervised/request",
    response_model=SupervisedTrainingJobResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def request_supervised_training(
    payload: SupervisedTrainingJobCreate,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> SupervisedTrainingJobResponse:
    return training_service.request_supervised_training(
        session=session,
        principal=principal,
        payload=payload,
        event_broadcaster=event_broadcaster,
    )


@router.get(
    "/supervised/{job_id}",
    response_model=SupervisedTrainingStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_supervised_training_status(
    job_id: int,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> SupervisedTrainingStatusResponse:
    del principal
    return training_service.get_supervised_training_status(session=session, job_id=job_id)


@router.post(
    "/supervised/{job_id}/retry",
    response_model=SupervisedTrainingJobResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def retry_supervised_training(
    job_id: int,
    principal: AuthPrincipal = Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
    event_broadcaster: EventBroadcaster = Depends(get_event_broadcaster),
) -> SupervisedTrainingJobResponse:
    return training_service.retry_supervised_training(
        session=session,
        principal=principal,
        job_id=job_id,
        event_broadcaster=event_broadcaster,
    )
