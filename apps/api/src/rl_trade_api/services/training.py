"""Training-request intake helpers used to trigger upstream ingestion."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_api.schemas.training import TrainingRequestCreate, TrainingRequestResponse
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.ingestion import create_ingestion_job, enqueue_ingestion_job
from rl_trade_data import IngestionJob, JobStatus, Symbol, TrainingRequest


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
