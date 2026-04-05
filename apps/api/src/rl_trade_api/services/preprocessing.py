"""API helpers for preprocessing job creation and dispatch."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.preprocessing import PreprocessingJobResponse, PreprocessingRequest
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_data import JobKind, JobStatus, PreprocessingJob, Symbol, mark_job_failed
from rl_trade_data.models import Timeframe


class _LazyPreprocessingTaskHandle:
    @staticmethod
    def delay(*, job_id: int) -> None:
        from rl_trade_worker.tasks import run_preprocessing_job as preprocessing_task

        preprocessing_task.delay(job_id=job_id)


run_preprocessing_job = _LazyPreprocessingTaskHandle()


def request_preprocessing(
    *,
    session: Session,
    principal: AuthPrincipal,
    payload: PreprocessingRequest,
    event_broadcaster: EventBroadcaster | None = None,
) -> PreprocessingJobResponse:
    normalized_symbol_code = payload.symbol_code.strip().upper()
    symbol = session.scalar(select(Symbol).where(Symbol.code == normalized_symbol_code))
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validated symbol {normalized_symbol_code} was not found.",
        )

    if payload.primary_timeframe not in payload.timeframes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="primary_timeframe must be included in timeframes.",
        )

    job = PreprocessingJob(
        symbol_id=symbol.id,
        status=JobStatus.PENDING,
        requested_timeframes=[timeframe.value for timeframe in payload.timeframes],
        details={
            "primary_timeframe": payload.primary_timeframe.value,
            "feature_set_name": payload.feature_set_name,
            "feature_set_version": payload.feature_set_version,
            "indicator_window": payload.indicator_window,
            "label_horizon_bars": payload.label_horizon_bars,
            "label_min_move_ratio": payload.label_min_move_ratio,
            "requested_by": principal.subject,
        },
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    try:
        _enqueue_preprocessing_job(job_id=job.id)
    except Exception as exc:
        mark_job_failed(
            session,
            job_kind=JobKind.PREPROCESSING,
            job_id=job.id,
            error_message=f"enqueue_failed: {exc}",
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to enqueue preprocessing job.",
        ) from exc
    _publish_preprocessing_event(
        event_broadcaster=event_broadcaster,
        job=job,
        symbol=symbol,
        source="api_request",
    )

    return build_preprocessing_job_response(job=job, symbol=symbol)


def build_preprocessing_job_response(*, job: PreprocessingJob, symbol: Symbol) -> PreprocessingJobResponse:
    details = job.details or {}
    return PreprocessingJobResponse(
        job_id=job.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        status=job.status,
        requested_timeframes=[Timeframe(value) for value in job.requested_timeframes],
        primary_timeframe=Timeframe(str(details.get("primary_timeframe", "1m"))),
        feature_set_name=str(details.get("feature_set_name", "baseline_forex")),
        feature_set_version=str(details.get("feature_set_version", "v1")),
        progress_percent=job.progress_percent,
        dataset_version_id=job.dataset_version_id,
    )


def _enqueue_preprocessing_job(*, job_id: int) -> None:
    run_preprocessing_job.delay(job_id=job_id)


def _publish_preprocessing_event(
    *,
    event_broadcaster: EventBroadcaster | None,
    job: PreprocessingJob,
    symbol: Symbol,
    source: str,
) -> None:
    if event_broadcaster is None:
        return
    details = dict(job.details or {})
    event_broadcaster.publish_event(
        event_type="preprocessing_progress",
        entity_type="preprocessing_job",
        entity_id=str(job.id),
        occurred_at=job.updated_at,
        payload={
            "job_id": job.id,
            "symbol_id": symbol.id,
            "symbol_code": symbol.code,
            "status": job.status.value,
            "progress_percent": job.progress_percent,
            "requested_timeframes": list(job.requested_timeframes),
            "primary_timeframe": details.get("primary_timeframe"),
            "feature_set_name": details.get("feature_set_name"),
            "feature_set_version": details.get("feature_set_version"),
            "source": source,
        },
    )
