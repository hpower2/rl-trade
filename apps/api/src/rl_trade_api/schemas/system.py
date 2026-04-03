"""Health and system status schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class APIInfoResponse(BaseModel):
    service: Literal["api"]
    status: str
    environment: str
    paper_trading_only: bool


class ComponentHealthResponse(BaseModel):
    name: str
    status: Literal["ok", "unavailable", "degraded"]
    details: dict[str, Any] = Field(default_factory=dict)


class SystemStatusResponse(BaseModel):
    service: Literal["api"] = "api"
    status: Literal["ok", "degraded"]
    environment: str
    paper_trading_only: bool
    components: dict[str, ComponentHealthResponse]
