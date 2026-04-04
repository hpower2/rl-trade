"""RL-training execution helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from rl_trade_common import Settings
from rl_trade_data import (
    DatasetVersion,
    FeatureSet,
    JobStatus,
    ModelArtifact,
    RLModel,
    RLTrainingJob,
    Symbol,
    TrainingRequest,
)
from rl_trade_data.models import ArtifactType, DatasetStatus, ModelStatus, Timeframe
from rl_trade_ml import save_ppo_artifacts, train_ppo_policy
from rl_trade_worker.services.preprocessing import (
    DEFAULT_FEATURE_SET_NAME,
    DEFAULT_FEATURE_SET_VERSION,
    DEFAULT_INDICATOR_WINDOW,
    DEFAULT_LABEL_HORIZON_BARS,
    DEFAULT_LABEL_MIN_MOVE_RATIO,
    build_preprocessing_dataset,
    load_candles_by_timeframe,
)


def perform_rl_training_job(
    *,
    session: Session,
    settings: Settings,
    job_id: int,
    progress_callback: Callable[[int, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    job = session.get(RLTrainingJob, job_id)
    if job is None:
        raise ValueError(f"RL training job {job_id} does not exist.")
    if job.dataset_version_id is None:
        raise ValueError(f"RL training job {job_id} does not have a dataset version.")

    training_request = session.get(TrainingRequest, job.training_request_id)
    if training_request is None:
        raise ValueError(f"Training request {job.training_request_id} does not exist.")

    dataset_version = session.get(DatasetVersion, job.dataset_version_id)
    if dataset_version is None:
        raise ValueError(f"Dataset version {job.dataset_version_id} does not exist.")
    if dataset_version.status is not DatasetStatus.READY:
        raise ValueError(f"Dataset version {dataset_version.id} is not ready for training.")

    symbol = session.get(Symbol, dataset_version.symbol_id)
    if symbol is None:
        raise ValueError(f"Symbol {dataset_version.symbol_id} does not exist.")

    feature_set = session.get(FeatureSet, dataset_version.feature_set_id)
    if feature_set is None:
        raise ValueError(f"Feature set {dataset_version.feature_set_id} does not exist.")

    training_request.status = JobStatus.RUNNING
    session.add(training_request)
    session.flush()

    included_timeframes = [Timeframe(value) for value in dataset_version.included_timeframes]
    dataset_details = dataset_version.details or {}
    if progress_callback is not None:
        progress_callback(10, {"phase": "rebuilding_dataset", "dataset_version_id": dataset_version.id})

    candles_by_timeframe = load_candles_by_timeframe(
        session=session,
        symbol_id=symbol.id,
        requested_timeframes=included_timeframes,
    )
    _, dataset = build_preprocessing_dataset(
        candles_by_timeframe=candles_by_timeframe,
        primary_timeframe=dataset_version.primary_timeframe,
        requested_timeframes=included_timeframes,
        indicator_window=int(dataset_details.get("indicator_window", DEFAULT_INDICATOR_WINDOW)),
        label_horizon_bars=int(dataset_details.get("label_horizon_bars", DEFAULT_LABEL_HORIZON_BARS)),
        label_min_move_ratio=Decimal(str(dataset_details.get("label_min_move_ratio", DEFAULT_LABEL_MIN_MOVE_RATIO))),
        feature_set_name=feature_set.name or DEFAULT_FEATURE_SET_NAME,
        feature_set_version=feature_set.version or DEFAULT_FEATURE_SET_VERSION,
    )

    if progress_callback is not None:
        progress_callback(40, {"phase": "training_policy", "row_count": dataset.row_count})

    hyperparameters = dict(job.hyperparameters or {})
    training = train_ppo_policy(
        dataset,
        window_size=int(hyperparameters.get("window_size", 8)),
        total_timesteps=int(hyperparameters.get("total_timesteps", 256)),
        n_steps=int(hyperparameters.get("n_steps", 32)),
        batch_size=int(hyperparameters.get("batch_size", 16)),
        learning_rate=float(hyperparameters.get("learning_rate", 3e-4)),
        gamma=float(hyperparameters.get("gamma", 0.99)),
        seed=int(hyperparameters.get("seed", 7)),
        atr_feature_name=str(hyperparameters.get("atr_feature_name", "atr_3")),
        spread_bps=float(hyperparameters.get("spread_bps", 1.0)),
        slippage_bps=float(hyperparameters.get("slippage_bps", 0.5)),
        overtrade_penalty=float(hyperparameters.get("overtrade_penalty", 0.05)),
        drawdown_penalty_factor=float(hyperparameters.get("drawdown_penalty_factor", 2.0)),
        rr_bonus=float(hyperparameters.get("rr_bonus", 0.1)),
    )

    if progress_callback is not None:
        progress_callback(75, {"phase": "writing_artifacts", "algorithm": training.algorithm})

    artifacts_dir = Path(settings.artifacts_root_dir).resolve() / f"symbol-{symbol.id}" / f"rl-job-{job.id}"
    checkpoint_path = save_ppo_artifacts(training=training, artifact_dir=artifacts_dir)
    feature_schema_path = artifacts_dir / "feature_schema.json"
    model_metadata_path = artifacts_dir / "model.json"
    metrics_path = artifacts_dir / "metrics.json"

    model_version_tag = f"{dataset_version.version_tag}-{training.algorithm}-job{job.id}"
    model = RLModel(
        training_job_id=job.id,
        symbol_id=symbol.id,
        dataset_version_id=dataset_version.id,
        status=ModelStatus.TRAINED,
        model_name=str(hyperparameters.get("model_name", "ppo_policy")),
        version_tag=model_version_tag,
        algorithm=training.algorithm,
        storage_uri=str(checkpoint_path),
        training_metrics=training.metrics,
        inference_config={
            "environment_name": training.environment_name,
            "feature_columns": list(training.feature_columns),
            "window_size": training.window_size,
            "action_map": {
                "0": "flat",
                "1": "long",
                "2": "short",
            },
            "device": training.device,
        },
    )
    session.add(model)
    session.flush()

    for artifact_type, path, details in [
        (ArtifactType.CONFIG, feature_schema_path, {"role": "feature_schema"}),
        (ArtifactType.CONFIG, model_metadata_path, {"role": "model_metadata"}),
        (ArtifactType.CHECKPOINT, checkpoint_path, {"algorithm": training.algorithm}),
        (ArtifactType.REPORT, metrics_path, {"role": "training_metrics"}),
    ]:
        session.add(
            ModelArtifact(
                rl_model_id=model.id,
                artifact_type=artifact_type,
                storage_uri=str(path),
                checksum=compute_checksum(path),
                size_bytes=path.stat().st_size,
                details=details,
            )
        )

    job.metrics = {
        **training.metrics,
        "model_id": model.id,
        "model_version_tag": model.version_tag,
        "artifact_dir": str(artifacts_dir),
    }
    training_request.status = JobStatus.SUCCEEDED
    session.add(training_request)
    session.add(job)
    session.flush()

    return {
        "job_id": job.id,
        "model_id": model.id,
        "algorithm": training.algorithm,
        "artifact_dir": str(artifacts_dir),
        "device": training.device,
    }


def compute_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
