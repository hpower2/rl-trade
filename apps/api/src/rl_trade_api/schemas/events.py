"""Schemas for live WebSocket event streaming."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EventType(str):
    VALIDATION_RESULT = "validation_result"
    INGESTION_PROGRESS = "ingestion_progress"
    PREPROCESSING_PROGRESS = "preprocessing_progress"
    TRAINING_PROGRESS = "training_progress"
    EVALUATION_STATUS = "evaluation_status"
    APPROVAL_STATUS = "approval_status"
    SIGNAL_EVENT = "signal_event"
    POSITION_UPDATE = "position_update"
    EQUITY_UPDATE = "equity_update"
    ALERT = "alert"


EVENT_TYPES: frozenset[str] = frozenset(
    {
        EventType.VALIDATION_RESULT,
        EventType.INGESTION_PROGRESS,
        EventType.PREPROCESSING_PROGRESS,
        EventType.TRAINING_PROGRESS,
        EventType.EVALUATION_STATUS,
        EventType.APPROVAL_STATUS,
        EventType.SIGNAL_EVENT,
        EventType.POSITION_UPDATE,
        EventType.EQUITY_UPDATE,
        EventType.ALERT,
    }
)


class EventEnvelope(BaseModel):
    schema_version: Literal[1] = 1
    cursor: int = Field(ge=1)
    event_id: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class WebSocketEventMessage(BaseModel):
    delivery: Literal["replay", "live"]
    event: EventEnvelope
