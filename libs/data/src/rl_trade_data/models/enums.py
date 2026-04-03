"""Shared enum types for the rl-trade persistence layer."""

from __future__ import annotations

from enum import Enum


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DatasetStatus(str, Enum):
    PENDING = "pending"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class TrainingType(str, Enum):
    SUPERVISED = "supervised"
    RL = "rl"


class ModelStatus(str, Enum):
    TRAINING = "training"
    TRAINED = "trained"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ArtifactType(str, Enum):
    CHECKPOINT = "checkpoint"
    WEIGHTS = "weights"
    SCALER = "scaler"
    CONFIG = "config"
    REPORT = "report"


class EvaluationType(str, Enum):
    VALIDATION = "validation"
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"


class ModelType(str, Enum):
    SUPERVISED = "supervised"
    RL = "rl"


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class TradeSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class SignalStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REJECTED = "rejected"
    EXECUTED = "executed"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"


class SystemLogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
