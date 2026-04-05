"""API helpers for ingestion job creation and dispatch."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.ingestion import IngestionJobResponse, IngestionRequest
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_data import IngestionJob, JobKind, JobStatus, Symbol, mark_job_failed, mark_job_requeued
from rl_trade_data.models.enums import Timeframe


class _LazyIngestionTaskHandle:
    @staticmethod
    def delay(*, job_id: int) -> None:
        from rl_trade_worker.tasks import run_ingestion_job as ingestion_task

        ingestion_task.delay(job_id=job_id)


run_ingestion_job = _LazyIngestionTaskHandle()


def request_ingestion(
    *,
    session: Session,
    principal: AuthPrincipal,
    payload: IngestionRequest,
    event_broadcaster: EventBroadcaster | None = None,
) -> IngestionJobResponse:
    normalized_symbol_code = payload.symbol_code.strip().upper()
    symbol = session.scalar(select(Symbol).where(Symbol.code == normalized_symbol_code))
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validated symbol {normalized_symbol_code} was not found.",
        )

    job = create_ingestion_job(
        session=session,
        symbol=symbol,
        requested_by=principal.subject,
        timeframes=payload.timeframes,
        sync_mode=payload.sync_mode,
        lookback_bars=payload.lookback_bars,
    )
    session.commit()
    session.refresh(job)

    enqueue_ingestion_job(
        session=session,
        job=job,
        failure_detail="Unable to enqueue ingestion job.",
    )
    _publish_ingestion_event(
        event_broadcaster=event_broadcaster,
        job=job,
        symbol=symbol,
        source="api_request",
    )

    return build_ingestion_job_response(job=job, symbol=symbol)


def retry_ingestion(
    *,
    session: Session,
    principal: AuthPrincipal,
    job_id: int,
    event_broadcaster: EventBroadcaster | None = None,
) -> IngestionJobResponse:
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job {job_id} was not found.",
        )

    if job.status is not JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ingestion job {job_id} cannot be retried from status {job.status.value}.",
        )

    symbol = session.get(Symbol, job.symbol_id)
    if symbol is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {job.symbol_id} for ingestion job {job_id} was not found.",
        )

    mark_job_requeued(
        session,
        job_kind=JobKind.INGESTION,
        job_id=job.id,
        requested_by=principal.subject,
    )
    session.commit()
    session.refresh(job)

    try:
        enqueue_ingestion_job(
            session=session,
            job=job,
            failure_detail="Unable to enqueue ingestion job retry.",
        )
    finally:
        session.refresh(job)
    _publish_ingestion_event(
        event_broadcaster=event_broadcaster,
        job=job,
        symbol=symbol,
        source="manual_retry",
    )

    return build_ingestion_job_response(job=job, symbol=symbol)


def create_ingestion_job(
    *,
    session: Session,
    symbol: Symbol,
    requested_by: str | None,
    timeframes: list[Timeframe],
    sync_mode: str,
    lookback_bars: int,
    details_update: dict[str, object] | None = None,
) -> IngestionJob:
    job = IngestionJob(
        symbol_id=symbol.id,
        status=JobStatus.PENDING,
        sync_mode=sync_mode,
        requested_by=requested_by,
        requested_timeframes=[timeframe.value for timeframe in timeframes],
        source_provider=symbol.provider,
        details={
            "lookback_bars": lookback_bars,
            **(details_update or {}),
        },
    )
    session.add(job)
    session.flush()
    return job


def enqueue_ingestion_job(
    *,
    session: Session,
    job: IngestionJob,
    failure_detail: str,
    on_failure: Callable[[Exception], None] | None = None,
) -> None:
    try:
        _enqueue_ingestion_job(job_id=job.id)
    except Exception as exc:
        mark_job_failed(
            session,
            job_kind=JobKind.INGESTION,
            job_id=job.id,
            error_message=f"enqueue_failed: {exc}",
        )
        if on_failure is not None:
            on_failure(exc)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=failure_detail,
        ) from exc


def _enqueue_ingestion_job(*, job_id: int) -> None:
    run_ingestion_job.delay(job_id=job_id)


def _publish_ingestion_event(
    *,
    event_broadcaster: EventBroadcaster | None,
    job: IngestionJob,
    symbol: Symbol,
    source: str,
) -> None:
    if event_broadcaster is None:
        return
    event_broadcaster.publish_event(
        event_type="ingestion_progress",
        entity_type="ingestion_job",
        entity_id=str(job.id),
        occurred_at=job.updated_at,
        payload={
            "job_id": job.id,
            "symbol_id": symbol.id,
            "symbol_code": symbol.code,
            "status": job.status.value,
            "progress_percent": job.progress_percent,
            "sync_mode": job.sync_mode,
            "requested_timeframes": list(job.requested_timeframes),
            "source_provider": job.source_provider,
            "source": source,
        },
    )


def build_ingestion_job_response(*, job: IngestionJob, symbol: Symbol) -> IngestionJobResponse:
    return IngestionJobResponse(
        job_id=job.id,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        status=job.status,
        sync_mode=job.sync_mode,
        requested_timeframes=[payload_value for payload_value in job.requested_timeframes],
        source_provider=job.source_provider,
        progress_percent=job.progress_percent,
        candles_requested=job.candles_requested,
        candles_written=job.candles_written,
        last_successful_candle_time=job.last_successful_candle_time,
    )
