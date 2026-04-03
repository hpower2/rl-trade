"""Authentication and session response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    authenticated: Literal[True] = True
    auth_mode: Literal["disabled", "static_token"]
    subject: str
    roles: list[str] = Field(default_factory=list)
