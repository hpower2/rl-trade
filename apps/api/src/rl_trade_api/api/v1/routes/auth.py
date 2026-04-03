"""Authentication/session endpoints."""

from fastapi import APIRouter, Depends

from rl_trade_api.api.deps import require_authenticated_principal
from rl_trade_api.schemas.auth import SessionResponse
from rl_trade_api.schemas.errors import ErrorResponse
from rl_trade_api.services import auth as auth_service
from rl_trade_api.services.auth import AuthPrincipal

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/session",
    response_model=SessionResponse,
    responses={401: {"model": ErrorResponse}},
)
def read_session(
    principal: AuthPrincipal = Depends(require_authenticated_principal),
) -> SessionResponse:
    return auth_service.build_session_response(principal)
