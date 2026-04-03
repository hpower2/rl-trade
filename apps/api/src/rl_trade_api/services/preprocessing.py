"""API helpers for preprocessing job creation and dispatch."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.preprocessing import PreprocessingJobResponse, PreprocessingRequest
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_data import JobKind, JobStatus, PreprocessingJob, Symbol, mark_job_failed
from rl_trade_data.models import Timeframe
from rl_trade_worker.tasks import run_preprocessing_job


def request_preprocessing(
    *,
    session: Session,
    principal: AuthPrincipal,
    payload: PreprocessingRequest,
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
        run_preprocessing_job.delay(job_id=job.id)
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
