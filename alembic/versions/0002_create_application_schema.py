"""Create the initial rl-trade application schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_create_application_schema"
down_revision = "0001_enable_timescaledb"
branch_labels = None
depends_on = None


def _created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def _updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def _timeframe_enum() -> sa.Enum:
    return sa.Enum("1m", "5m", "15m", name="timeframe_enum", native_enum=False)


def _job_status_enum() -> sa.Enum:
    return sa.Enum("pending", "running", "succeeded", "failed", "cancelled", name="job_status_enum", native_enum=False)


def _dataset_status_enum() -> sa.Enum:
    return sa.Enum("pending", "building", "ready", "failed", "archived", name="dataset_status_enum", native_enum=False)


def _training_type_enum() -> sa.Enum:
    return sa.Enum("supervised", "rl", name="training_type_enum", native_enum=False)


def _model_status_enum() -> sa.Enum:
    return sa.Enum(
        "training",
        "trained",
        "evaluated",
        "approved",
        "rejected",
        "archived",
        name="model_status_enum",
        native_enum=False,
    )


def _artifact_type_enum() -> sa.Enum:
    return sa.Enum("checkpoint", "weights", "scaler", "config", "report", name="artifact_type_enum", native_enum=False)


def _evaluation_type_enum() -> sa.Enum:
    return sa.Enum("validation", "backtest", "paper_trading", name="evaluation_type_enum", native_enum=False)


def _model_type_enum() -> sa.Enum:
    return sa.Enum("supervised", "rl", name="model_type_enum", native_enum=False)


def _connection_status_enum() -> sa.Enum:
    return sa.Enum("connected", "disconnected", "error", name="connection_status_enum", native_enum=False)


def _trade_side_enum() -> sa.Enum:
    return sa.Enum("long", "short", name="trade_side_enum", native_enum=False)


def _signal_status_enum() -> sa.Enum:
    return sa.Enum("pending", "accepted", "expired", "rejected", "executed", name="signal_status_enum", native_enum=False)


def _order_type_enum() -> sa.Enum:
    return sa.Enum("market", "limit", "stop", name="order_type_enum", native_enum=False)


def _order_status_enum() -> sa.Enum:
    return sa.Enum("pending", "submitted", "filled", "cancelled", "rejected", name="order_status_enum", native_enum=False)


def _position_status_enum() -> sa.Enum:
    return sa.Enum("open", "closed", name="position_status_enum", native_enum=False)


def _audit_outcome_enum() -> sa.Enum:
    return sa.Enum("success", "failure", "blocked", name="audit_outcome_enum", native_enum=False)


def _system_log_level_enum() -> sa.Enum:
    return sa.Enum("debug", "info", "warning", "error", name="system_log_level_enum", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("quote_currency", sa.String(length=8), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default=sa.text("'mt5'")),
        sa.Column("asset_class", sa.String(length=32), nullable=False, server_default=sa.text("'forex'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("code", name="uq_symbols_code"),
    )
    op.create_index("ix_symbols_provider_code", "symbols", ["provider", "code"])

    op.create_table(
        "feature_sets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_columns", sa.JSON(), nullable=False),
        sa.Column("indicator_columns", sa.JSON(), nullable=False),
        sa.Column("pattern_columns", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("name", "version", name="uq_feature_sets_name_version"),
    )

    op.create_table(
        "mt5_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_login", sa.BigInteger(), nullable=False),
        sa.Column("server_name", sa.String(length=128), nullable=False),
        sa.Column("account_name", sa.String(length=128), nullable=True),
        sa.Column("account_currency", sa.String(length=16), nullable=True),
        sa.Column("leverage", sa.Integer(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "connection_status",
            _connection_status_enum(),
            nullable=False,
            server_default=sa.text("'disconnected'"),
        ),
        sa.Column("is_trade_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("account_login", "server_name", name="uq_mt5_accounts_login_server"),
    )
    op.create_index("ix_mt5_accounts_connection_status", "mt5_accounts", ["connection_status", "updated_at"])

    op.create_table(
        "symbol_validation_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_symbol", sa.String(length=32), nullable=False),
        sa.Column("normalized_symbol", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default=sa.text("'mt5'")),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        _created_at_column(),
    )
    op.create_index("ix_symbol_validation_results_symbol_id", "symbol_validation_results", ["symbol_id"])
    op.create_index(
        "ix_symbol_validation_results_requested_symbol",
        "symbol_validation_results",
        ["requested_symbol", "validated_at"],
    )

    op.create_table(
        "ohlc_candles",
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timeframe", _timeframe_enum(), nullable=False),
        sa.Column("candle_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 8), nullable=False),
        sa.Column("high", sa.Numeric(18, 8), nullable=False),
        sa.Column("low", sa.Numeric(18, 8), nullable=False),
        sa.Column("close", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.Numeric(18, 8), nullable=False, server_default=sa.text("0")),
        sa.Column("spread", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default=sa.text("'mt5'")),
        sa.Column("source", sa.String(length=64), nullable=False, server_default=sa.text("'historical'")),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        _created_at_column(),
        sa.PrimaryKeyConstraint("symbol_id", "timeframe", "candle_time", name="pk_ohlc_candles"),
        sa.CheckConstraint("high >= low", name="ck_ohlc_candles_high_gte_low"),
        sa.CheckConstraint("open >= low", name="ck_ohlc_candles_open_gte_low"),
        sa.CheckConstraint("close >= low", name="ck_ohlc_candles_close_gte_low"),
        sa.CheckConstraint("high >= open", name="ck_ohlc_candles_high_gte_open"),
        sa.CheckConstraint("high >= close", name="ck_ohlc_candles_high_gte_close"),
        sa.CheckConstraint("volume >= 0", name="ck_ohlc_candles_non_negative_volume"),
    )
    op.create_index("ix_ohlc_candles_symbol_id", "ohlc_candles", ["symbol_id"])
    op.create_index("ix_ohlc_candles_symbol_timeframe_time", "ohlc_candles", ["symbol_id", "timeframe", "candle_time"])
    op.create_index("ix_ohlc_candles_candle_time", "ohlc_candles", ["candle_time"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", _job_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("sync_mode", sa.String(length=32), nullable=False, server_default=sa.text("'incremental'")),
        sa.Column("requested_by", sa.String(length=64), nullable=True),
        sa.Column("requested_timeframes", sa.JSON(), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False, server_default=sa.text("'mt5'")),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("candles_requested", sa.Integer(), nullable=True),
        sa.Column("candles_written", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_successful_candle_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index("ix_ingestion_jobs_symbol_id", "ingestion_jobs", ["symbol_id"])
    op.create_index("ix_ingestion_jobs_status_created_at", "ingestion_jobs", ["status", "created_at"])
    op.create_index("ix_ingestion_jobs_symbol_created_at", "ingestion_jobs", ["symbol_id", "created_at"])

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_set_id", sa.Integer(), sa.ForeignKey("feature_sets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", _dataset_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("primary_timeframe", _timeframe_enum(), nullable=False),
        sa.Column("included_timeframes", sa.JSON(), nullable=False),
        sa.Column("label_name", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("data_hash", sa.String(length=128), nullable=True),
        sa.Column("storage_uri", sa.String(length=512), nullable=True),
        sa.Column("candle_start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("candle_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        _created_at_column(),
        sa.UniqueConstraint("symbol_id", "feature_set_id", "version_tag", name="uq_dataset_versions_symbol_feature_version"),
    )
    op.create_index("ix_dataset_versions_symbol_id", "dataset_versions", ["symbol_id"])
    op.create_index("ix_dataset_versions_feature_set_id", "dataset_versions", ["feature_set_id"])
    op.create_index("ix_dataset_versions_status_created_at", "dataset_versions", ["status", "created_at"])

    op.create_table(
        "preprocessing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_set_id", sa.Integer(), sa.ForeignKey("feature_sets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", _job_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("requested_timeframes", sa.JSON(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index("ix_preprocessing_jobs_symbol_id", "preprocessing_jobs", ["symbol_id"])
    op.create_index("ix_preprocessing_jobs_feature_set_id", "preprocessing_jobs", ["feature_set_id"])
    op.create_index("ix_preprocessing_jobs_dataset_version_id", "preprocessing_jobs", ["dataset_version_id"])
    op.create_index("ix_preprocessing_jobs_status_created_at", "preprocessing_jobs", ["status", "created_at"])

    op.create_table(
        "training_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("training_type", _training_type_enum(), nullable=False),
        sa.Column("status", _job_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("requested_by", sa.String(length=64), nullable=True),
        sa.Column("requested_timeframes", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index("ix_training_requests_symbol_id", "training_requests", ["symbol_id"])
    op.create_index("ix_training_requests_dataset_version_id", "training_requests", ["dataset_version_id"])
    op.create_index("ix_training_requests_status_created_at", "training_requests", ["status", "created_at"])
    op.create_index("ix_training_requests_training_type", "training_requests", ["training_type", "created_at"])

    op.create_table(
        "supervised_training_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("training_request_id", sa.Integer(), sa.ForeignKey("training_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", _job_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("queue_name", sa.String(length=64), nullable=False, server_default=sa.text("'supervised_training'")),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hyperparameters", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index("ix_supervised_training_jobs_training_request_id", "supervised_training_jobs", ["training_request_id"])
    op.create_index("ix_supervised_training_jobs_dataset_version_id", "supervised_training_jobs", ["dataset_version_id"])
    op.create_index("ix_supervised_training_jobs_status_created_at", "supervised_training_jobs", ["status", "created_at"])

    op.create_table(
        "rl_training_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("training_request_id", sa.Integer(), sa.ForeignKey("training_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", _job_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("queue_name", sa.String(length=64), nullable=False, server_default=sa.text("'rl_training'")),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("environment_name", sa.String(length=128), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hyperparameters", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
    )
    op.create_index("ix_rl_training_jobs_training_request_id", "rl_training_jobs", ["training_request_id"])
    op.create_index("ix_rl_training_jobs_dataset_version_id", "rl_training_jobs", ["dataset_version_id"])
    op.create_index("ix_rl_training_jobs_status_created_at", "rl_training_jobs", ["status", "created_at"])

    op.create_table(
        "supervised_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("training_job_id", sa.Integer(), sa.ForeignKey("supervised_training_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("feature_set_id", sa.Integer(), sa.ForeignKey("feature_sets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", _model_status_enum(), nullable=False, server_default=sa.text("'training'")),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("storage_uri", sa.String(length=512), nullable=True),
        sa.Column("training_metrics", sa.JSON(), nullable=True),
        sa.Column("inference_config", sa.JSON(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("training_job_id", name="uq_supervised_models_training_job_id"),
        sa.UniqueConstraint("symbol_id", "model_name", "version_tag", name="uq_supervised_models_symbol_name_version"),
    )
    op.create_index("ix_supervised_models_symbol_id", "supervised_models", ["symbol_id"])
    op.create_index("ix_supervised_models_training_job_id", "supervised_models", ["training_job_id"])
    op.create_index("ix_supervised_models_dataset_version_id", "supervised_models", ["dataset_version_id"])
    op.create_index("ix_supervised_models_feature_set_id", "supervised_models", ["feature_set_id"])
    op.create_index("ix_supervised_models_status_created_at", "supervised_models", ["status", "created_at"])

    op.create_table(
        "rl_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("training_job_id", sa.Integer(), sa.ForeignKey("rl_training_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", _model_status_enum(), nullable=False, server_default=sa.text("'training'")),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("storage_uri", sa.String(length=512), nullable=True),
        sa.Column("training_metrics", sa.JSON(), nullable=True),
        sa.Column("inference_config", sa.JSON(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("training_job_id", name="uq_rl_models_training_job_id"),
        sa.UniqueConstraint("symbol_id", "model_name", "version_tag", name="uq_rl_models_symbol_name_version"),
    )
    op.create_index("ix_rl_models_symbol_id", "rl_models", ["symbol_id"])
    op.create_index("ix_rl_models_training_job_id", "rl_models", ["training_job_id"])
    op.create_index("ix_rl_models_dataset_version_id", "rl_models", ["dataset_version_id"])
    op.create_index("ix_rl_models_status_created_at", "rl_models", ["status", "created_at"])

    op.create_table(
        "model_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("supervised_model_id", sa.Integer(), sa.ForeignKey("supervised_models.id", ondelete="CASCADE"), nullable=True),
        sa.Column("rl_model_id", sa.Integer(), sa.ForeignKey("rl_models.id", ondelete="CASCADE"), nullable=True),
        sa.Column("artifact_type", _artifact_type_enum(), nullable=False),
        sa.Column("storage_uri", sa.String(length=512), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        _created_at_column(),
        sa.CheckConstraint(
            "(supervised_model_id IS NOT NULL AND rl_model_id IS NULL) OR "
            "(supervised_model_id IS NULL AND rl_model_id IS NOT NULL)",
            name="ck_model_artifacts_exactly_one_model",
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_model_artifacts_non_negative_size"),
    )
    op.create_index("ix_model_artifacts_supervised_model_id", "model_artifacts", ["supervised_model_id"])
    op.create_index("ix_model_artifacts_rl_model_id", "model_artifacts", ["rl_model_id"])

    op.create_table(
        "model_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("supervised_model_id", sa.Integer(), sa.ForeignKey("supervised_models.id", ondelete="CASCADE"), nullable=True),
        sa.Column("rl_model_id", sa.Integer(), sa.ForeignKey("rl_models.id", ondelete="CASCADE"), nullable=True),
        sa.Column("dataset_version_id", sa.Integer(), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluation_type", _evaluation_type_enum(), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=False),
        sa.Column("risk_to_reward", sa.Numeric(8, 4), nullable=False),
        sa.Column("sharpe_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(8, 4), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        _created_at_column(),
        sa.CheckConstraint(
            "(supervised_model_id IS NOT NULL AND rl_model_id IS NULL) OR "
            "(supervised_model_id IS NULL AND rl_model_id IS NOT NULL)",
            name="ck_model_evaluations_exactly_one_model",
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 100", name="ck_model_evaluations_confidence_bounds"),
        sa.CheckConstraint("risk_to_reward >= 0", name="ck_model_evaluations_non_negative_rr"),
    )
    op.create_index("ix_model_evaluations_supervised_model_id", "model_evaluations", ["supervised_model_id"])
    op.create_index("ix_model_evaluations_rl_model_id", "model_evaluations", ["rl_model_id"])
    op.create_index("ix_model_evaluations_dataset_version_id", "model_evaluations", ["dataset_version_id"])
    op.create_index("ix_model_evaluations_evaluated_at", "model_evaluations", ["evaluated_at"])

    op.create_table(
        "approved_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supervised_model_id", sa.Integer(), sa.ForeignKey("supervised_models.id", ondelete="CASCADE"), nullable=True),
        sa.Column("rl_model_id", sa.Integer(), sa.ForeignKey("rl_models.id", ondelete="CASCADE"), nullable=True),
        sa.Column("model_type", _model_type_enum(), nullable=False),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=False),
        sa.Column("risk_to_reward", sa.Numeric(8, 4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.UniqueConstraint("supervised_model_id", name="uq_approved_models_supervised_model_id"),
        sa.UniqueConstraint("rl_model_id", name="uq_approved_models_rl_model_id"),
        sa.CheckConstraint(
            "(supervised_model_id IS NOT NULL AND rl_model_id IS NULL AND model_type = 'supervised') OR "
            "(supervised_model_id IS NULL AND rl_model_id IS NOT NULL AND model_type = 'rl')",
            name="ck_approved_models_exactly_one_model",
        ),
        sa.CheckConstraint("confidence >= 70", name="ck_approved_models_min_confidence"),
        sa.CheckConstraint("risk_to_reward >= 2.0", name="ck_approved_models_min_risk_reward"),
    )
    op.create_index("ix_approved_models_symbol_id", "approved_models", ["symbol_id"])
    op.create_index("ix_approved_models_supervised_model_id", "approved_models", ["supervised_model_id"])
    op.create_index("ix_approved_models_rl_model_id", "approved_models", ["rl_model_id"])
    op.create_index("ix_approved_models_symbol_active", "approved_models", ["symbol_id", "is_active"])

    op.create_table(
        "paper_trade_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approved_model_id", sa.Integer(), sa.ForeignKey("approved_models.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("timeframe", _timeframe_enum(), nullable=False),
        sa.Column("side", _trade_side_enum(), nullable=False),
        sa.Column("status", _signal_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("signal_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(18, 8), nullable=False),
        sa.Column("take_profit", sa.Numeric(18, 8), nullable=False),
        sa.Column("rationale", sa.JSON(), nullable=True),
        _created_at_column(),
    )
    op.create_index("ix_paper_trade_signals_symbol_id", "paper_trade_signals", ["symbol_id"])
    op.create_index("ix_paper_trade_signals_approved_model_id", "paper_trade_signals", ["approved_model_id"])
    op.create_index("ix_paper_trade_signals_signal_time", "paper_trade_signals", ["signal_time"])
    op.create_index("ix_paper_trade_signals_status_created_at", "paper_trade_signals", ["status", "created_at"])

    op.create_table(
        "paper_trade_orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("paper_trade_signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mt5_account_id", sa.Integer(), sa.ForeignKey("mt5_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("side", _trade_side_enum(), nullable=False),
        sa.Column("order_type", _order_type_enum(), nullable=False, server_default=sa.text("'market'")),
        sa.Column("status", _order_status_enum(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("broker_order_id", sa.String(length=128), nullable=True),
        sa.Column("requested_quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(18, 8), nullable=True),
        sa.Column("requested_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("filled_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(18, 8), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("broker_order_id", name="uq_paper_trade_orders_broker_order_id"),
    )
    op.create_index("ix_paper_trade_orders_symbol_id", "paper_trade_orders", ["symbol_id"])
    op.create_index("ix_paper_trade_orders_signal_id", "paper_trade_orders", ["signal_id"])
    op.create_index("ix_paper_trade_orders_mt5_account_id", "paper_trade_orders", ["mt5_account_id"])
    op.create_index("ix_paper_trade_orders_status_created_at", "paper_trade_orders", ["status", "created_at"])

    op.create_table(
        "paper_trade_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("paper_trade_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("side", _trade_side_enum(), nullable=False),
        sa.Column("status", _position_status_enum(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("open_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(18, 8), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(18, 8), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=True),
        _created_at_column(),
        _updated_at_column(),
        sa.UniqueConstraint("order_id", name="uq_paper_trade_positions_order_id"),
    )
    op.create_index("ix_paper_trade_positions_symbol_id", "paper_trade_positions", ["symbol_id"])
    op.create_index("ix_paper_trade_positions_order_id", "paper_trade_positions", ["order_id"])
    op.create_index("ix_paper_trade_positions_status_created_at", "paper_trade_positions", ["status", "created_at"])

    op.create_table(
        "trade_executions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("paper_trade_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("paper_trade_positions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("execution_type", sa.String(length=64), nullable=False),
        sa.Column("execution_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("commission", sa.Numeric(18, 8), nullable=True),
        sa.Column("slippage", sa.Numeric(18, 8), nullable=True),
        sa.Column("raw_execution", sa.JSON(), nullable=True),
        _created_at_column(),
    )
    op.create_index("ix_trade_executions_order_id", "trade_executions", ["order_id"])
    op.create_index("ix_trade_executions_position_id", "trade_executions", ["position_id"])
    op.create_index("ix_trade_executions_execution_time", "trade_executions", ["execution_time"])

    op.create_table(
        "equity_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mt5_account_id", sa.Integer(), sa.ForeignKey("mt5_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("balance", sa.Numeric(18, 8), nullable=False),
        sa.Column("equity", sa.Numeric(18, 8), nullable=False),
        sa.Column("margin", sa.Numeric(18, 8), nullable=True),
        sa.Column("free_margin", sa.Numeric(18, 8), nullable=True),
        sa.Column("open_positions_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("details", sa.JSON(), nullable=True),
        _created_at_column(),
        sa.UniqueConstraint("mt5_account_id", "snapshot_time", name="uq_equity_snapshots_account_snapshot_time"),
    )
    op.create_index("ix_equity_snapshots_mt5_account_id", "equity_snapshots", ["mt5_account_id"])
    op.create_index("ix_equity_snapshots_snapshot_time", "equity_snapshots", ["snapshot_time"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("outcome", _audit_outcome_enum(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        _created_at_column(),
    )
    op.create_index("ix_audit_logs_entity_lookup", "audit_logs", ["entity_type", "entity_id", "created_at"])

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("level", _system_log_level_enum(), nullable=False),
        sa.Column("event", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        _created_at_column(),
    )
    op.create_index("ix_system_logs_service_level_created_at", "system_logs", ["service", "level", "created_at"])


def downgrade() -> None:
    op.drop_table("system_logs")
    op.drop_table("audit_logs")
    op.drop_table("equity_snapshots")
    op.drop_table("trade_executions")
    op.drop_table("paper_trade_positions")
    op.drop_table("paper_trade_orders")
    op.drop_table("paper_trade_signals")
    op.drop_table("approved_models")
    op.drop_table("model_evaluations")
    op.drop_table("model_artifacts")
    op.drop_table("rl_models")
    op.drop_table("supervised_models")
    op.drop_table("rl_training_jobs")
    op.drop_table("supervised_training_jobs")
    op.drop_table("training_requests")
    op.drop_table("preprocessing_jobs")
    op.drop_table("dataset_versions")
    op.drop_table("ingestion_jobs")
    op.drop_table("ohlc_candles")
    op.drop_table("symbol_validation_results")
    op.drop_table("mt5_accounts")
    op.drop_table("feature_sets")
    op.drop_table("symbols")
