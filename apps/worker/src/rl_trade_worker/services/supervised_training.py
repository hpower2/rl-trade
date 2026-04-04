"""Supervised-training execution helpers."""

from __future__ import annotations

import hashlib
import json
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
    SupervisedModel,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
)
from rl_trade_data.models import ArtifactType, DatasetStatus, ModelStatus, Timeframe
from rl_trade_ml.supervised import artifact_payload, train_supervised_baselines, train_torch_mlp
from rl_trade_worker.services.preprocessing import (
    DEFAULT_FEATURE_SET_NAME,
    DEFAULT_FEATURE_SET_VERSION,
    DEFAULT_INDICATOR_WINDOW,
    DEFAULT_LABEL_HORIZON_BARS,
    DEFAULT_LABEL_MIN_MOVE_RATIO,
    build_preprocessing_dataset,
    load_candles_by_timeframe,
)


def perform_supervised_training_job(
    *,
    session: Session,
    settings: Settings,
    job_id: int,
    progress_callback: Callable[[int, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    job = session.get(SupervisedTrainingJob, job_id)
    if job is None:
        raise ValueError(f"Supervised training job {job_id} does not exist.")

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
        progress_callback(40, {"phase": "training_baselines", "row_count": dataset.row_count})

    hyperparameters = dict(job.hyperparameters or {})
    if job.algorithm == "torch_mlp":
        training = train_torch_mlp(
            dataset,
            validation_ratio=float(hyperparameters.get("validation_ratio", 0.2)),
            walk_forward_folds=int(hyperparameters.get("walk_forward_folds", 3)),
            hidden_dim=int(hyperparameters.get("hidden_dim", 16)),
            epochs=int(hyperparameters.get("epochs", 25)),
            learning_rate=float(hyperparameters.get("learning_rate", 0.01)),
        )
    else:
        training = train_supervised_baselines(
            dataset,
            validation_ratio=float(hyperparameters.get("validation_ratio", 0.2)),
            walk_forward_folds=int(hyperparameters.get("walk_forward_folds", 3)),
        )

    if progress_callback is not None:
        progress_callback(75, {"phase": "writing_artifacts", "algorithm": training.chosen_algorithm})

    artifacts_dir = Path(settings.artifacts_root_dir).resolve() / f"symbol-{symbol.id}" / f"supervised-job-{job.id}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    feature_schema_path = write_json_artifact(
        artifacts_dir / "feature_schema.json",
        {
            "feature_columns": list(training.feature_columns),
            "label_name": training.label_name,
            "primary_timeframe": dataset_version.primary_timeframe.value,
            "included_timeframes": list(dataset_version.included_timeframes),
        },
    )
    scaler_path = write_json_artifact(
        artifacts_dir / "scaler.json",
        {
            "means": training.scaler.means,
            "stds": training.scaler.stds,
        },
    )
    model_path = (
        write_torch_checkpoint(artifacts_dir / "checkpoint.pt", training.checkpoint_state)
        if training.checkpoint_state is not None
        else write_json_artifact(artifacts_dir / "model.json", artifact_payload(training))
    )
    metrics_path = write_json_artifact(artifacts_dir / "metrics.json", training.metrics)

    model_version_tag = f"{dataset_version.version_tag}-{training.chosen_algorithm}-job{job.id}"
    model = SupervisedModel(
        training_job_id=job.id,
        symbol_id=symbol.id,
        dataset_version_id=dataset_version.id,
        feature_set_id=feature_set.id,
        status=ModelStatus.TRAINED,
        model_name=str(hyperparameters.get("model_name", "baseline_classifier")),
        version_tag=model_version_tag,
        algorithm=training.chosen_algorithm,
        storage_uri=str(model_path),
        training_metrics=training.metrics,
        inference_config={
            "feature_columns": list(training.feature_columns),
            "output_classes": ["buy", "sell", "no_trade"],
            "confidence_key": "confidence",
            "setup_quality_key": "setup_quality",
            "device": training.device,
        },
    )
    session.add(model)
    session.flush()

    for artifact_type, path, details in [
        (ArtifactType.CONFIG, feature_schema_path, {"role": "feature_schema"}),
        (ArtifactType.SCALER, scaler_path, {"role": "standard_scaler"}),
        (ArtifactType.CHECKPOINT, model_path, {"algorithm": training.chosen_algorithm}),
        (ArtifactType.REPORT, metrics_path, {"role": "training_metrics"}),
    ]:
        session.add(
            ModelArtifact(
                supervised_model_id=model.id,
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
        "algorithm": training.chosen_algorithm,
        "artifact_dir": str(artifacts_dir),
        "device": training.device,
    }


def write_json_artifact(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    return path


def compute_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_torch_checkpoint(path: Path, payload: dict[str, Any] | None) -> Path:
    if payload is None:
        raise ValueError("Torch checkpoint payload is required.")
    import torch

    torch.save(payload, path)
    return path
