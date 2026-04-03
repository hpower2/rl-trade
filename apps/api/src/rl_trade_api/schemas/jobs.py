"""API schemas for tracked background jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from rl_trade_data import JobKind, JobStatus


class JobStatusResponse(BaseModel):
    job_type: JobKind
    job_id: int
    status: JobStatus
    queue_name: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress_percent: int
    symbol_id: int | None = None
    error_message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
