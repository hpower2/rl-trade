"""Symbol validation request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SymbolValidationRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)


class SymbolValidationResponse(BaseModel):
    validation_result_id: int
    symbol_id: int | None = None
    requested_symbol: str
    normalized_input: str
    normalized_symbol: str | None = None
    provider: str
    is_valid: bool
    reason: str | None = None
    base_currency: str | None = None
    quote_currency: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
