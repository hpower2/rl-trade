"""Preprocessing request endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rl_trade_api.api.deps import get_db_session, require_authenticated_principal
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.schemas.preprocessing import PreprocessingJobResponse, PreprocessingRequest
from rl_trade_api.services import preprocessing as preprocessing_service
from rl_trade_api.services.auth import AuthPrincipal

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
) -> PreprocessingJobResponse:
    return preprocessing_service.request_preprocessing(session=session, principal=principal, payload=payload)
