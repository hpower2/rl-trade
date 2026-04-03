"""Job polling service helpers."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from rl_trade_api.schemas.jobs import JobStatusResponse
from rl_trade_data import JobKind, get_job, get_job_queue_name


def get_job_status(*, session: Session, job_type: JobKind, job_id: int) -> JobStatusResponse:
    job = get_job(session, job_kind=job_type, job_id=job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{job_type.value} job {job_id} was not found.",
        )

    return JobStatusResponse(
        job_type=job_type,
        job_id=job.id,
        status=job.status,
        queue_name=get_job_queue_name(job_type, job),
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress_percent=job.progress_percent,
        symbol_id=getattr(job, "symbol_id", None),
        error_message=job.error_message,
        details=job.details or {},
    )
