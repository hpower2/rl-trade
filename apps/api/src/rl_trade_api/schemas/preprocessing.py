"""Preprocessing request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rl_trade_data import JobStatus
from rl_trade_data.models import Timeframe


class PreprocessingRequest(BaseModel):
    symbol_code: str = Field(min_length=1, max_length=32)
    timeframes: list[Timeframe] = Field(default_factory=lambda: [Timeframe.M1, Timeframe.M5, Timeframe.M15])
    primary_timeframe: Timeframe = Timeframe.M1
    feature_set_name: str = Field(default="baseline_forex", min_length=1, max_length=128)
    feature_set_version: str = Field(default="v1", min_length=1, max_length=64)
    indicator_window: int = Field(default=3, ge=1, le=200)
    label_horizon_bars: int = Field(default=2, ge=1, le=500)
    label_min_move_ratio: str = Field(default="0.0005", min_length=1, max_length=32)


class PreprocessingJobResponse(BaseModel):
    job_id: int
    symbol_id: int
    symbol_code: str
    status: JobStatus
    requested_timeframes: list[Timeframe]
    primary_timeframe: Timeframe
    feature_set_name: str
    feature_set_version: str
    progress_percent: int
    dataset_version_id: int | None = None

