"""Training-request intake helpers for ingestion and supervised jobs."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.training import (
    ModelArtifactResponse,
    SupervisedTrainingJobCreate,
    SupervisedTrainingJobResponse,
    SupervisedTrainingStatusResponse,
    SupervisedModelResponse,
    TrainingRequestCreate,
    TrainingRequestResponse,
)
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_api.services.ingestion import create_ingestion_job, enqueue_ingestion_job
from rl_trade_data import (
    DatasetVersion,
    IngestionJob,
    JobKind,
    JobStatus,
    ModelArtifact,
    SupervisedModel,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    mark_job_failed,
    mark_job_requeued,
)
from rl_trade_data.models import DatasetStatus, TrainingType


class _LazySupervisedTrainingTaskHandle:
    @staticmethod
    def delay(*, job_id: int) -> None:
        from rl_trade_worker.tasks import run_supervised_training_job as supervised_training_task

        supervised_training_task.delay(job_id=job_id)


run_supervised_training_job = _LazySupervisedTrainingTaskHandle()


def request_training(
    *,
    session: Session,
    principal: AuthPrincipal,
    payload: TrainingRequestCreate,
) -> TrainingRequestResponse:
    normalized_symbol_code = payload.symbol_code.strip().upper()
    symbol = session.scalar(select(Symbol).where(Symbol.code == normalized_symbol_code))
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validated symbol {normalized_symbol_code} was not found.",
        )

    training_request = TrainingRequest(
        symbol_id=symbol.id,
        training_type=payload.training_type,
        status=JobStatus.PENDING,
        priority=payload.priority,
        requested_by=principal.subject,
        requested_timeframes=[timeframe.value for timeframe in payload.timeframes],
        notes=payload.notes,
    )
    session.add(training_request)
    session.flush()

    ingestion_job = create_ingestion_job(
        session=session,
        symbol=symbol,
        requested_by=principal.subject,
        timeframes=payload.timeframes,
        sync_mode=payload.sync_mode,
        lookback_bars=payload.lookback_bars,
        details_update={
            "trigger": "training_request",
            "training_request_id": training_request.id,
            "training_type": payload.training_type.value,
        },
    )
    session.commit()
    session.refresh(training_request)
    session.refresh(ingestion_job)

    def mark_training_request_failed(_: Exception) -> None:
        training_request.status = JobStatus.FAILED
        session.add(training_request)

    enqueue_ingestion_job(
        session=session,
        job=ingestion_job,
        failure_detail="Unable to enqueue ingestion job for training request.",
        on_failure=mark_training_request_failed,
    )

    return build_training_request_response(
        training_request=training_request,
        ingestion_job=ingestion_job,
        symbol=symbol,
    )


def build_training_request_response(
    *,
    training_request: TrainingRequest,
    ingestion_job: IngestionJob,
    symbol: Symbol,
) -> TrainingRequestResponse:
    return TrainingRequestResponse(
        training_request_id=training_request.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        training_type=training_request.training_type,
        status=training_request.status,
        requested_timeframes=[timeframe for timeframe in training_request.requested_timeframes],
        ingestion_job_id=ingestion_job.id,
        ingestion_job_status=ingestion_job.status,
    )


def request_supervised_training(
    *,
    session: Session,
    principal: AuthPrincipal,
    payload: SupervisedTrainingJobCreate,
    event_broadcaster: EventBroadcaster | None = None,
) -> SupervisedTrainingJobResponse:
    dataset_version = session.get(DatasetVersion, payload.dataset_version_id)
    if dataset_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset version {payload.dataset_version_id} was not found.",
        )
    if dataset_version.status is not DatasetStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset version {payload.dataset_version_id} is not ready for training.",
        )

    symbol = session.get(Symbol, dataset_version.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {dataset_version.symbol_id} for dataset version {dataset_version.id} was not found.",
        )

    training_request = TrainingRequest(
        symbol_id=symbol.id,
        dataset_version_id=dataset_version.id,
        training_type=TrainingType.SUPERVISED,
        status=JobStatus.PENDING,
        priority=payload.priority,
        requested_by=principal.subject,
        requested_timeframes=list(dataset_version.included_timeframes),
        notes=payload.notes,
    )
    session.add(training_request)
    session.flush()

    training_job = SupervisedTrainingJob(
        training_request_id=training_request.id,
        dataset_version_id=dataset_version.id,
        status=JobStatus.PENDING,
        algorithm=payload.algorithm,
        hyperparameters={
            "model_name": payload.model_name,
            "validation_ratio": payload.validation_ratio,
            "walk_forward_folds": payload.walk_forward_folds,
            "hidden_dim": payload.hidden_dim,
            "epochs": payload.epochs,
            "learning_rate": payload.learning_rate,
        },
    )
    session.add(training_job)
    session.commit()
    session.refresh(training_request)
    session.refresh(training_job)

    try:
        _enqueue_supervised_training_job(job_id=training_job.id)
    except Exception as exc:
        training_request.status = JobStatus.FAILED
        session.add(training_request)
        mark_job_failed(
            session,
            job_kind=JobKind.SUPERVISED_TRAINING,
            job_id=training_job.id,
            error_message=f"enqueue_failed: {exc}",
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to enqueue supervised training job.",
        ) from exc

    _publish_supervised_training_event(
        event_broadcaster=event_broadcaster,
        training_job=training_job,
        training_request=training_request,
        symbol=symbol,
        source="api_request",
    )

    return SupervisedTrainingJobResponse(
        training_request_id=training_request.id,
        supervised_training_job_id=training_job.id,
        dataset_version_id=dataset_version.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        algorithm=training_job.algorithm,
        status=training_job.status,
    )


def get_supervised_training_status(
    *,
    session: Session,
    job_id: int,
) -> SupervisedTrainingStatusResponse:
    training_job = session.get(SupervisedTrainingJob, job_id)
    if training_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supervised training job {job_id} was not found.",
        )

    training_request = session.get(TrainingRequest, training_job.training_request_id)
    if training_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training request {training_job.training_request_id} was not found.",
        )

    dataset_version = session.get(DatasetVersion, training_job.dataset_version_id)
    if dataset_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset version {training_job.dataset_version_id} was not found.",
        )

    symbol = session.get(Symbol, training_request.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {training_request.symbol_id} was not found.",
        )

    model = session.scalar(
        select(SupervisedModel).where(SupervisedModel.training_job_id == training_job.id)
    )
    artifacts: list[ModelArtifact] = []
    if model is not None:
        artifacts = (
            session.execute(
                select(ModelArtifact).where(ModelArtifact.supervised_model_id == model.id)
            )
            .scalars()
            .all()
        )

    return SupervisedTrainingStatusResponse(
        training_request_id=training_request.id,
        supervised_training_job_id=training_job.id,
        dataset_version_id=dataset_version.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        algorithm=training_job.algorithm,
        status=training_job.status,
        progress_percent=training_job.progress_percent,
        metrics=dict(training_job.metrics or {}),
        model=(
            SupervisedModelResponse(
                model_id=model.id,
                model_name=model.model_name,
                version_tag=model.version_tag,
                algorithm=model.algorithm,
                storage_uri=model.storage_uri,
                status=model.status.value,
                inference_config=dict(model.inference_config or {}),
            )
            if model is not None
            else None
        ),
        artifacts=[
            ModelArtifactResponse(
                artifact_type=artifact.artifact_type.value,
                storage_uri=artifact.storage_uri,
                size_bytes=artifact.size_bytes,
                checksum=artifact.checksum,
                details=dict(artifact.details or {}),
            )
            for artifact in artifacts
        ],
    )


def retry_supervised_training(
    *,
    session: Session,
    principal: AuthPrincipal,
    job_id: int,
    event_broadcaster: EventBroadcaster | None = None,
) -> SupervisedTrainingJobResponse:
    training_job = session.get(SupervisedTrainingJob, job_id)
    if training_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supervised training job {job_id} was not found.",
        )
    if training_job.status is not JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Supervised training job {job_id} cannot be retried from status {training_job.status.value}.",
        )

    training_request = session.get(TrainingRequest, training_job.training_request_id)
    if training_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training request {training_job.training_request_id} was not found.",
        )

    dataset_version = session.get(DatasetVersion, training_job.dataset_version_id)
    if dataset_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset version {training_job.dataset_version_id} was not found.",
        )
    if dataset_version.status is not DatasetStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset version {dataset_version.id} is not ready for training.",
        )

    symbol = session.get(Symbol, training_request.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {training_request.symbol_id} was not found.",
        )

    existing_model = session.scalar(
        select(SupervisedModel).where(SupervisedModel.training_job_id == training_job.id)
    )
    if existing_model is not None:
        artifacts = (
            session.execute(
                select(ModelArtifact).where(ModelArtifact.supervised_model_id == existing_model.id)
            )
            .scalars()
            .all()
        )
        for artifact in artifacts:
            session.delete(artifact)
        session.delete(existing_model)
        session.flush()

    mark_job_requeued(
        session,
        job_kind=JobKind.SUPERVISED_TRAINING,
        job_id=training_job.id,
        requested_by=principal.subject,
    )
    training_job.metrics = None
    training_request.status = JobStatus.PENDING
    session.add(training_job)
    session.add(training_request)
    session.commit()
    session.refresh(training_job)
    session.refresh(training_request)

    try:
        _enqueue_supervised_training_job(job_id=training_job.id)
    except Exception as exc:
        training_request.status = JobStatus.FAILED
        session.add(training_request)
        mark_job_failed(
            session,
            job_kind=JobKind.SUPERVISED_TRAINING,
            job_id=training_job.id,
            error_message=f"enqueue_failed: {exc}",
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to enqueue supervised training retry.",
        ) from exc

    _publish_supervised_training_event(
        event_broadcaster=event_broadcaster,
        training_job=training_job,
        training_request=training_request,
        symbol=symbol,
        source="manual_retry",
    )

    return SupervisedTrainingJobResponse(
        training_request_id=training_request.id,
        supervised_training_job_id=training_job.id,
        dataset_version_id=dataset_version.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        algorithm=training_job.algorithm,
        status=training_job.status,
    )


def _enqueue_supervised_training_job(*, job_id: int) -> None:
    run_supervised_training_job.delay(job_id=job_id)


def _publish_supervised_training_event(
    *,
    event_broadcaster: EventBroadcaster | None,
    training_job: SupervisedTrainingJob,
    training_request: TrainingRequest,
    symbol: Symbol,
    source: str,
) -> None:
    if event_broadcaster is None:
        return
    event_broadcaster.publish_event(
        event_type="training_progress",
        entity_type="supervised_training_job",
        entity_id=str(training_job.id),
        occurred_at=training_job.updated_at,
        payload={
            "job_id": training_job.id,
            "training_request_id": training_request.id,
            "dataset_version_id": training_job.dataset_version_id,
            "symbol_id": symbol.id,
            "symbol_code": symbol.code,
            "algorithm": training_job.algorithm,
            "status": training_job.status.value,
            "progress_percent": training_job.progress_percent,
            "source": source,
        },
    )
