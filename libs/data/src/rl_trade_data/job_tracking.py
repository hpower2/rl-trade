"""Shared job lookup and state update helpers."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from rl_trade_data.models import IngestionJob, JobStatus, PreprocessingJob, RLTrainingJob, SupervisedTrainingJob
from rl_trade_data.models.mixins import utcnow


class JobKind(str, Enum):
    INGESTION = "ingestion"
    PREPROCESSING = "preprocessing"
    SUPERVISED_TRAINING = "supervised_training"
    RL_TRAINING = "rl_training"


TrackedJob = IngestionJob | PreprocessingJob | SupervisedTrainingJob | RLTrainingJob

JOB_MODEL_BY_KIND: dict[JobKind, type[TrackedJob]] = {
    JobKind.INGESTION: IngestionJob,
    JobKind.PREPROCESSING: PreprocessingJob,
    JobKind.SUPERVISED_TRAINING: SupervisedTrainingJob,
    JobKind.RL_TRAINING: RLTrainingJob,
}


def get_job(session: Session, *, job_kind: JobKind, job_id: int) -> TrackedJob | None:
    return session.get(JOB_MODEL_BY_KIND[job_kind], job_id)


def require_job(session: Session, *, job_kind: JobKind, job_id: int) -> TrackedJob:
    job = get_job(session, job_kind=job_kind, job_id=job_id)
    if job is None:
        raise LookupError(f"{job_kind.value} job {job_id} does not exist.")
    return job


def update_job_progress(
    session: Session,
    *,
    job_kind: JobKind,
    job_id: int,
    progress_percent: int,
    details_update: dict[str, Any] | None = None,
) -> TrackedJob:
    job = require_job(session, job_kind=job_kind, job_id=job_id)
    job.progress_percent = max(0, min(progress_percent, 100))
    if details_update:
        job.details = _merge_details(job.details, details_update)
    session.flush()
    return job


def mark_job_running(
    session: Session,
    *,
    job_kind: JobKind,
    job_id: int,
    started_at: datetime | None = None,
    details_update: dict[str, Any] | None = None,
) -> TrackedJob:
    job = require_job(session, job_kind=job_kind, job_id=job_id)
    job.status = JobStatus.RUNNING
    job.started_at = job.started_at or started_at or utcnow()
    job.finished_at = None
    job.error_message = None
    if details_update:
        job.details = _merge_details(job.details, details_update)
    session.flush()
    return job


def mark_job_retry(
    session: Session,
    *,
    job_kind: JobKind,
    job_id: int,
    retry_count: int,
    reason: str,
) -> TrackedJob:
    job = require_job(session, job_kind=job_kind, job_id=job_id)
    job.status = JobStatus.PENDING
    job.error_message = None
    job.details = _merge_details(
        job.details,
        {
            "retry_count": retry_count,
            "last_retry_reason": reason,
        },
    )
    session.flush()
    return job


def mark_job_requeued(
    session: Session,
    *,
    job_kind: JobKind,
    job_id: int,
    requested_by: str | None = None,
) -> TrackedJob:
    job = require_job(session, job_kind=job_kind, job_id=job_id)
    job.status = JobStatus.PENDING
    job.progress_percent = 0
    job.started_at = None
    job.finished_at = None
    job.error_message = None

    if hasattr(job, "candles_requested"):
        job.candles_requested = None
    if hasattr(job, "candles_written"):
        job.candles_written = 0
    if hasattr(job, "last_successful_candle_time"):
        job.last_successful_candle_time = None

    manual_retry_count = int((job.details or {}).get("manual_retry_count", 0)) + 1
    details_update = {
        "manual_retry_count": manual_retry_count,
        "last_manual_retry_at": utcnow().isoformat(),
    }
    if requested_by:
        details_update["last_manual_retry_by"] = requested_by

    job.details = _merge_details(job.details, details_update)
    session.flush()
    return job


def mark_job_succeeded(
    session: Session,
    *,
    job_kind: JobKind,
    job_id: int,
    finished_at: datetime | None = None,
    details_update: dict[str, Any] | None = None,
) -> TrackedJob:
    job = require_job(session, job_kind=job_kind, job_id=job_id)
    job.status = JobStatus.SUCCEEDED
    job.progress_percent = 100
    job.finished_at = finished_at or utcnow()
    job.error_message = None
    if details_update:
        job.details = _merge_details(job.details, details_update)
    session.flush()
    return job


def mark_job_failed(
    session: Session,
    *,
    job_kind: JobKind,
    job_id: int,
    error_message: str,
    finished_at: datetime | None = None,
) -> TrackedJob:
    job = require_job(session, job_kind=job_kind, job_id=job_id)
    job.status = JobStatus.FAILED
    job.finished_at = finished_at or utcnow()
    job.error_message = error_message
    session.flush()
    return job


def get_job_queue_name(job_kind: JobKind, job: TrackedJob) -> str:
    return getattr(job, "queue_name", "") or job_kind.value


def _merge_details(
    existing: dict[str, Any] | None,
    updates: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(existing or {})
    merged.update(updates)
    return merged
