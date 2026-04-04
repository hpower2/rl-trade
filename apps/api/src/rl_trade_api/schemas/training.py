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


class SupervisedTrainingJobCreate(BaseModel):
    dataset_version_id: int = Field(ge=1)
    algorithm: str = Field(default="auto_baseline", min_length=1, max_length=64)
    model_name: str = Field(default="baseline_classifier", min_length=1, max_length=128)
    validation_ratio: float = Field(default=0.2, gt=0.0, lt=0.5)
    walk_forward_folds: int = Field(default=3, ge=1, le=10)
    hidden_dim: int = Field(default=16, ge=4, le=512)
    epochs: int = Field(default=25, ge=1, le=500)
    learning_rate: float = Field(default=0.01, gt=0.0, le=1.0)
    priority: int = Field(default=100, ge=1, le=1000)
    notes: str | None = Field(default=None, max_length=2000)


class SupervisedTrainingJobResponse(BaseModel):
    training_request_id: int
    supervised_training_job_id: int
    dataset_version_id: int
    symbol_id: int
    symbol_code: str
    algorithm: str
    status: JobStatus


class ModelArtifactResponse(BaseModel):
    artifact_type: str
    storage_uri: str
    size_bytes: int | None = None
    checksum: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class SupervisedModelResponse(BaseModel):
    model_id: int
    model_name: str
    version_tag: str
    algorithm: str
    storage_uri: str | None = None
    status: str
    inference_config: dict[str, object] = Field(default_factory=dict)


class SupervisedTrainingStatusResponse(BaseModel):
    training_request_id: int
    supervised_training_job_id: int
    dataset_version_id: int
    symbol_id: int
    symbol_code: str
    algorithm: str
    status: JobStatus
    progress_percent: int
    metrics: dict[str, object] = Field(default_factory=dict)
    model: SupervisedModelResponse | None = None
    artifacts: list[ModelArtifactResponse] = Field(default_factory=list)
