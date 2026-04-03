"""Training request intake endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_db_session, require_authenticated_principal
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.training import TrainingRequestCreate, TrainingRequestResponse
from rl_trade_api.services import training as training_service
from rl_trade_api.services.auth import AuthPrincipal

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
