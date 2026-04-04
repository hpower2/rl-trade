"""Persistence models for model training, evaluation, and approvals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from rl_trade_data.db.base import Base
from rl_trade_data.models.enums import ArtifactType, EvaluationType, JobStatus, ModelStatus, ModelType
from rl_trade_data.models.mixins import CreatedAtMixin, IntegerPrimaryKeyMixin, SymbolForeignKeyMixin, TimestampMixin


class SupervisedTrainingJob(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supervised_training_jobs"
    __table_args__ = (
        sa.Index("ix_supervised_training_jobs_status_created_at", "status", "created_at"),
    )

    training_request_id: Mapped[int] = mapped_column(
        sa.ForeignKey("training_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        sa.Enum(JobStatus, name="job_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
    )
    queue_name: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="supervised_training")
    algorithm: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    progress_percent: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    hyperparameters: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)


class RLTrainingJob(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rl_training_jobs"
    __table_args__ = (
        sa.Index("ix_rl_training_jobs_status_created_at", "status", "created_at"),
    )

    training_request_id: Mapped[int] = mapped_column(
        sa.ForeignKey("training_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        sa.Enum(JobStatus, name="job_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
    )
    queue_name: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="rl_training")
    algorithm: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    environment_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    progress_percent: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    hyperparameters: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)


class SupervisedModel(IntegerPrimaryKeyMixin, TimestampMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "supervised_models"
    __table_args__ = (
        sa.UniqueConstraint("training_job_id", name="uq_supervised_models_training_job_id"),
        sa.UniqueConstraint("symbol_id", "model_name", "version_tag", name="uq_supervised_models_symbol_name_version"),
        sa.Index("ix_supervised_models_status_created_at", "status", "created_at"),
    )

    training_job_id: Mapped[int] = mapped_column(
        sa.ForeignKey("supervised_training_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    feature_set_id: Mapped[int] = mapped_column(
        sa.ForeignKey("feature_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[ModelStatus] = mapped_column(
        sa.Enum(ModelStatus, name="model_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=ModelStatus.TRAINING,
        server_default=ModelStatus.TRAINING.value,
    )
    model_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    version_tag: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    training_metrics: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    inference_config: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class RLModel(IntegerPrimaryKeyMixin, TimestampMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "rl_models"
    __table_args__ = (
        sa.UniqueConstraint("training_job_id", name="uq_rl_models_training_job_id"),
        sa.UniqueConstraint("symbol_id", "model_name", "version_tag", name="uq_rl_models_symbol_name_version"),
        sa.Index("ix_rl_models_status_created_at", "status", "created_at"),
    )

    training_job_id: Mapped[int] = mapped_column(
        sa.ForeignKey("rl_training_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ModelStatus] = mapped_column(
        sa.Enum(ModelStatus, name="model_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=ModelStatus.TRAINING,
        server_default=ModelStatus.TRAINING.value,
    )
    model_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    version_tag: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    training_metrics: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    inference_config: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class ModelArtifact(IntegerPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "model_artifacts"
    __table_args__ = (
        sa.CheckConstraint(
            "(supervised_model_id IS NOT NULL AND rl_model_id IS NULL) OR "
            "(supervised_model_id IS NULL AND rl_model_id IS NOT NULL)",
            name="ck_model_artifacts_exactly_one_model",
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_model_artifacts_non_negative_size"),
    )

    supervised_model_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("supervised_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    rl_model_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("rl_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        sa.Enum(ArtifactType, name="artifact_type_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    storage_uri: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    checksum: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger(), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class ModelEvaluation(IntegerPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "model_evaluations"
    __table_args__ = (
        sa.CheckConstraint(
            "(supervised_model_id IS NOT NULL AND rl_model_id IS NULL) OR "
            "(supervised_model_id IS NULL AND rl_model_id IS NOT NULL)",
            name="ck_model_evaluations_exactly_one_model",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 100", name="ck_model_evaluations_confidence_bounds"),
        sa.CheckConstraint("risk_to_reward >= 0", name="ck_model_evaluations_non_negative_rr"),
        sa.Index("ix_model_evaluations_evaluated_at", "evaluated_at"),
    )

    supervised_model_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("supervised_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    rl_model_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("rl_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    dataset_version_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evaluation_type: Mapped[EvaluationType] = mapped_column(
        sa.Enum(EvaluationType, name="evaluation_type_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    risk_to_reward: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 4), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 4), nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class ApprovedModel(IntegerPrimaryKeyMixin, CreatedAtMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "approved_models"
    __table_args__ = (
        sa.UniqueConstraint("supervised_model_id", name="uq_approved_models_supervised_model_id"),
        sa.UniqueConstraint("rl_model_id", name="uq_approved_models_rl_model_id"),
        sa.CheckConstraint(
            "(supervised_model_id IS NOT NULL AND rl_model_id IS NULL AND model_type = 'supervised') OR "
            "(supervised_model_id IS NULL AND rl_model_id IS NOT NULL AND model_type = 'rl')",
            name="ck_approved_models_exactly_one_model",
        ),
        sa.CheckConstraint("confidence >= 70", name="ck_approved_models_min_confidence"),
        sa.CheckConstraint("risk_to_reward >= 2.0", name="ck_approved_models_min_risk_reward"),
        sa.Index("ix_approved_models_symbol_active", "symbol_id", "is_active"),
    )

    supervised_model_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("supervised_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    rl_model_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("rl_models.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    model_type: Mapped[ModelType] = mapped_column(
        sa.Enum(
            ModelType,
            name="model_type_enum",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    approved_by: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    risk_to_reward: Mapped[Decimal] = mapped_column(sa.Numeric(8, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True, server_default=sa.true())
    approved_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
