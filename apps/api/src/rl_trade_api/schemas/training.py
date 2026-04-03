"""Training request intake schemas used for ingestion orchestration."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rl_trade_data import JobStatus
from rl_trade_data.models.enums import Timeframe, TrainingType


class TrainingRequestCreate(BaseModel):
    symbol_code: str = Field(min_length=1, max_length=32)
    training_type: TrainingType
    timeframes: list[Timeframe] = Field(default_factory=lambda: [Timeframe.M1, Timeframe.M5, Timeframe.M15])
    sync_mode: str = Field(default="incremental", pattern="^(backfill|incremental)$")
    lookback_bars: int = Field(default=500, ge=1, le=5000)
    priority: int = Field(default=100, ge=1, le=1000)
    notes: str | None = Field(default=None, max_length=2000)


class TrainingRequestResponse(BaseModel):
    training_request_id: int
    symbol_id: int
    symbol_code: str
    training_type: TrainingType
    status: JobStatus
    requested_timeframes: list[Timeframe]
    ingestion_job_id: int
    ingestion_job_status: JobStatus

