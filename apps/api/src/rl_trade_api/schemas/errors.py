"""API error response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
