"""Authentication helpers and session scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import compare_digest
from typing import Literal

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from rl_trade_common import Settings
from rl_trade_api.schemas.auth import SessionResponse


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    subject: str
    roles: tuple[str, ...]
    auth_mode: Literal["disabled", "static_token"]


def resolve_principal(
    *,
    settings: Settings,
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthPrincipal | None:
    if settings.api_auth_mode == "disabled":
        return AuthPrincipal(
            subject=settings.api_auth_subject,
            roles=("operator",),
            auth_mode="disabled",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    expected_token = settings.api_auth_token.get_secret_value() if settings.api_auth_token else ""
    presented_token = credentials.credentials.strip()
    if not presented_token or not compare_digest(presented_token, expected_token):
        return None

    return AuthPrincipal(
        subject=settings.api_auth_subject,
        roles=("operator",),
        auth_mode="static_token",
    )


def authentication_required_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def build_session_response(principal: AuthPrincipal) -> SessionResponse:
    return SessionResponse(
        authenticated=True,
        auth_mode=principal.auth_mode,
        subject=principal.subject,
        roles=list(principal.roles),
    )
