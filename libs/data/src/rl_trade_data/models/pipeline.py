"""Persistence models for ingestion, preprocessing, and training requests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from rl_trade_data.db.base import Base
from rl_trade_data.models.enums import DatasetStatus, JobStatus, Timeframe, TrainingType
from rl_trade_data.models.mixins import CreatedAtMixin, IntegerPrimaryKeyMixin, SymbolForeignKeyMixin, TimestampMixin


class IngestionJob(IntegerPrimaryKeyMixin, TimestampMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        sa.Index("ix_ingestion_jobs_status_created_at", "status", "created_at"),
        sa.Index("ix_ingestion_jobs_symbol_created_at", "symbol_id", "created_at"),
    )

    status: Mapped[JobStatus] = mapped_column(
        sa.Enum(JobStatus, name="job_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
    )
    sync_mode: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="incremental")
    requested_by: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    requested_timeframes: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    source_provider: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="mt5")
    progress_percent: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    candles_requested: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    candles_written: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    last_successful_candle_time: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class FeatureSet(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feature_sets"
    __table_args__ = (
        sa.UniqueConstraint("name", "version", name="uq_feature_sets_name_version"),
    )

    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    feature_columns: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    indicator_columns: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    pattern_columns: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class DatasetVersion(IntegerPrimaryKeyMixin, CreatedAtMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        sa.UniqueConstraint("symbol_id", "feature_set_id", "version_tag", name="uq_dataset_versions_symbol_feature_version"),
        sa.Index("ix_dataset_versions_status_created_at", "status", "created_at"),
    )

    feature_set_id: Mapped[int] = mapped_column(
        sa.ForeignKey("feature_sets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[DatasetStatus] = mapped_column(
        sa.Enum(DatasetStatus, name="dataset_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=DatasetStatus.PENDING,
        server_default=DatasetStatus.PENDING.value,
    )
    version_tag: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    primary_timeframe: Mapped[Timeframe] = mapped_column(
        sa.Enum(Timeframe, name="timeframe_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    included_timeframes: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    label_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    row_count: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    data_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    storage_uri: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    candle_start_time: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    candle_end_time: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class PreprocessingJob(IntegerPrimaryKeyMixin, TimestampMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "preprocessing_jobs"
    __table_args__ = (
        sa.Index("ix_preprocessing_jobs_status_created_at", "status", "created_at"),
    )

    feature_set_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("feature_sets.id", ondelete="SET NULL"),
        nullable=True,
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
    requested_timeframes: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    progress_percent: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(sa.JSON(), nullable=True)


class TrainingRequest(IntegerPrimaryKeyMixin, TimestampMixin, SymbolForeignKeyMixin, Base):
    __tablename__ = "training_requests"
    __table_args__ = (
        sa.Index("ix_training_requests_status_created_at", "status", "created_at"),
        sa.Index("ix_training_requests_training_type", "training_type", "created_at"),
    )

    dataset_version_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    training_type: Mapped[TrainingType] = mapped_column(
        sa.Enum(TrainingType, name="training_type_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        sa.Enum(JobStatus, name="job_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=JobStatus.PENDING,
        server_default=JobStatus.PENDING.value,
    )
    priority: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=100, server_default="100")
    requested_by: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    requested_timeframes: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
