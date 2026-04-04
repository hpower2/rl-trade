"""Schemas for model evaluations and approved symbol queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from rl_trade_data.models import EvaluationType, ModelType


class ModelEvaluationCreate(BaseModel):
    model_type: ModelType
    model_id: int = Field(ge=1)
    evaluation_type: EvaluationType = EvaluationType.VALIDATION
    dataset_version_id: int | None = Field(default=None, ge=1)
    confidence: float = Field(ge=0.0, le=100.0)
    risk_to_reward: float = Field(ge=0.0)
    sample_size: int = Field(ge=1)
    sharpe_ratio: float | None = None
    max_drawdown: float | None = Field(default=None, ge=0.0)
    has_critical_data_issue: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionResponse(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)
    min_confidence: float
    min_risk_reward: float
    min_sample_size: int
    max_approved_drawdown: float


class ModelEvaluationResponse(BaseModel):
    evaluation_id: int
    model_type: ModelType
    model_id: int
    symbol_id: int
    symbol_code: str
    evaluation_type: EvaluationType
    confidence: float
    risk_to_reward: float
    sample_size: int
    max_drawdown: float | None = None
    approved_model_id: int | None = None
    model_status: str
    decision: ApprovalDecisionResponse


class ModelRegistryEntryResponse(BaseModel):
    model_type: ModelType
    model_id: int
    symbol_id: int
    symbol_code: str
    dataset_version_id: int | None = None
    feature_set_id: int | None = None
    training_job_id: int
    model_name: str
    version_tag: str
    algorithm: str
    status: str
    storage_uri: str | None = None
    approved_model_id: int | None = None
    is_active_approval: bool
    created_at: datetime


class ModelEvaluationSummaryResponse(BaseModel):
    evaluation_id: int
    model_type: ModelType
    model_id: int
    symbol_id: int
    symbol_code: str
    dataset_version_id: int | None = None
    evaluation_type: EvaluationType
    confidence: float
    risk_to_reward: float
    sample_size: int | None = None
    max_drawdown: float | None = None
    approved: bool
    decision_reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime


class ApprovedSymbolResponse(BaseModel):
    approved_model_id: int
    symbol_id: int
    symbol_code: str
    model_type: ModelType
    model_id: int
    model_name: str
    algorithm: str
    confidence: float
    risk_to_reward: float
    approved_at: datetime
