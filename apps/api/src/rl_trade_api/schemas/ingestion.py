"""Ingestion request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from rl_trade_data.models.enums import JobStatus, Timeframe


class IngestionRequest(BaseModel):
    symbol_code: str = Field(min_length=1, max_length=32)
    timeframes: list[Timeframe] = Field(default_factory=lambda: [Timeframe.M1, Timeframe.M5, Timeframe.M15])
    sync_mode: Literal["backfill", "incremental"] = "incremental"
    lookback_bars: int = Field(default=500, ge=1, le=5000)


class IngestionJobResponse(BaseModel):
    job_id: int
    symbol_id: int
    symbol_code: str
    status: JobStatus
    sync_mode: str
    requested_timeframes: list[Timeframe]
    source_provider: str
    progress_percent: int
    candles_requested: int | None = None
    candles_written: int
    last_successful_candle_time: datetime | None = None
