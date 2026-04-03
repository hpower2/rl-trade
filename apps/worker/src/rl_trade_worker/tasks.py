"""Bootstrap task definitions for the worker service."""

from __future__ import annotations

from typing import Any

from rl_trade_common import get_settings
from rl_trade_data import JobKind, get_session_factory, session_scope
from rl_trade_trading import MT5Gateway
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.queues import INGESTION_QUEUE, MAINTENANCE_QUEUE, PREPROCESSING_QUEUE
from rl_trade_worker.services.ingestion import perform_ingestion_job
from rl_trade_worker.services.preprocessing import perform_preprocessing_job
from rl_trade_worker.task_base import TrackedTask, TransientTaskError


class IngestionProbeTask(TrackedTask):
    job_kind = JobKind.INGESTION


class IngestionTask(TrackedTask):
    job_kind = JobKind.INGESTION


class PreprocessingTask(TrackedTask):
    job_kind = JobKind.PREPROCESSING


@celery_app.task(name="system.ping", queue=MAINTENANCE_QUEUE)
def ping() -> dict[str, str]:
    return {"service": "worker", "status": "ok"}


@celery_app.task(
    bind=True,
    base=IngestionProbeTask,
    name="jobs.run_ingestion_probe",
    queue=INGESTION_QUEUE,
)
def run_ingestion_probe(
    self: TrackedTask,
    job_id: int,
    *,
    fail_until_attempt: int = 0,
    fail_hard: bool = False,
) -> dict[str, Any]:
    self.set_progress(job_id=job_id, progress_percent=25, details_update={"phase": "starting"})

    if fail_hard:
        raise ValueError("permanent probe failure")

    if self.request.retries < fail_until_attempt:
        raise TransientTaskError("transient probe failure")

    self.set_progress(job_id=job_id, progress_percent=90, details_update={"phase": "completed"})
    return {"job_id": job_id, "status": "completed"}


@celery_app.task(
    bind=True,
    base=IngestionTask,
    name="jobs.run_ingestion_job",
    queue=INGESTION_QUEUE,
)
def run_ingestion_job(self: TrackedTask, job_id: int) -> dict[str, Any]:
    session_factory = get_session_factory()
    gateway = MT5Gateway()
    settings = get_settings()

    with session_scope(session_factory) as session:
        return perform_ingestion_job(
            session=session,
            gateway=gateway,
            settings=settings,
            job_id=job_id,
            progress_callback=lambda progress, details=None: self.set_progress(
                job_id=job_id,
                progress_percent=progress,
                details_update=details,
            ),
        )


@celery_app.task(
    bind=True,
    base=PreprocessingTask,
    name="jobs.run_preprocessing_job",
    queue=PREPROCESSING_QUEUE,
)
def run_preprocessing_job(self: TrackedTask, job_id: int) -> dict[str, Any]:
    session_factory = get_session_factory()

    with session_scope(session_factory) as session:
        return perform_preprocessing_job(
            session=session,
            job_id=job_id,
            progress_callback=lambda progress, details=None: self.set_progress(
                job_id=job_id,
                progress_percent=progress,
                details_update=details,
            ),
        )
