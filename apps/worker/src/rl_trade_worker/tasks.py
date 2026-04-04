"""Bootstrap task definitions for the worker service."""

from __future__ import annotations

from typing import Any

from rl_trade_common import get_settings
from rl_trade_data import (
    JobKind,
    RLTrainingJob,
    SupervisedTrainingJob,
    TrainingRequest,
    get_session_factory,
    session_scope,
)
from rl_trade_data.models import JobStatus
from rl_trade_trading import MT5Gateway
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.queues import (
    INGESTION_QUEUE,
    MAINTENANCE_QUEUE,
    PREPROCESSING_QUEUE,
    RL_TRAINING_QUEUE,
    SUPERVISED_TRAINING_QUEUE,
)
from rl_trade_worker.services.ingestion import perform_ingestion_job
from rl_trade_worker.services.preprocessing import perform_preprocessing_job
from rl_trade_worker.services.rl_training import perform_rl_training_job
from rl_trade_worker.services.supervised_training import perform_supervised_training_job
from rl_trade_worker.task_base import TrackedTask, TransientTaskError


class IngestionProbeTask(TrackedTask):
    job_kind = JobKind.INGESTION


class IngestionTask(TrackedTask):
    job_kind = JobKind.INGESTION


class PreprocessingTask(TrackedTask):
    job_kind = JobKind.PREPROCESSING


class SupervisedTrainingTask(TrackedTask):
    job_kind = JobKind.SUPERVISED_TRAINING

    def before_start(self, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        super().before_start(task_id, args, kwargs)
        self._sync_training_request_status(args, kwargs, status=JobStatus.RUNNING)

    def on_retry(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        super().on_retry(exc, task_id, args, kwargs, einfo)
        self._sync_training_request_status(args, kwargs, status=JobStatus.PENDING)

    def on_success(
        self,
        retval: Any,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        super().on_success(retval, task_id, args, kwargs)
        self._sync_training_request_status(args, kwargs, status=JobStatus.SUCCEEDED)

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        super().on_failure(exc, task_id, args, kwargs, einfo)
        self._sync_training_request_status(args, kwargs, status=JobStatus.FAILED)

    def _sync_training_request_status(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        status: JobStatus,
    ) -> None:
        job_id = self._extract_job_id(args, kwargs)
        if job_id is None:
            return

        with session_scope(get_session_factory()) as session:
            job = session.get(SupervisedTrainingJob, job_id)
            if job is None:
                return
            training_request = session.get(TrainingRequest, job.training_request_id)
            if training_request is None:
                return
            training_request.status = status
            session.add(training_request)


class RLTrainingTask(TrackedTask):
    job_kind = JobKind.RL_TRAINING

    def before_start(self, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        super().before_start(task_id, args, kwargs)
        self._sync_training_request_status(args, kwargs, status=JobStatus.RUNNING)

    def on_retry(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        super().on_retry(exc, task_id, args, kwargs, einfo)
        self._sync_training_request_status(args, kwargs, status=JobStatus.PENDING)

    def on_success(
        self,
        retval: Any,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        super().on_success(retval, task_id, args, kwargs)
        self._sync_training_request_status(args, kwargs, status=JobStatus.SUCCEEDED)

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        super().on_failure(exc, task_id, args, kwargs, einfo)
        self._sync_training_request_status(args, kwargs, status=JobStatus.FAILED)

    def _sync_training_request_status(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        status: JobStatus,
    ) -> None:
        job_id = self._extract_job_id(args, kwargs)
        if job_id is None:
            return

        with session_scope(get_session_factory()) as session:
            job = session.get(RLTrainingJob, job_id)
            if job is None:
                return
            training_request = session.get(TrainingRequest, job.training_request_id)
            if training_request is None:
                return
            training_request.status = status
            session.add(training_request)


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


@celery_app.task(
    bind=True,
    base=SupervisedTrainingTask,
    name="jobs.run_supervised_training_job",
    queue=SUPERVISED_TRAINING_QUEUE,
)
def run_supervised_training_job(self: TrackedTask, job_id: int) -> dict[str, Any]:
    session_factory = get_session_factory()
    settings = get_settings()

    with session_scope(session_factory) as session:
        return perform_supervised_training_job(
            session=session,
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
    base=RLTrainingTask,
    name="jobs.run_rl_training_job",
    queue=RL_TRAINING_QUEUE,
)
def run_rl_training_job(self: TrackedTask, job_id: int) -> dict[str, Any]:
    session_factory = get_session_factory()
    settings = get_settings()

    with session_scope(session_factory) as session:
        return perform_rl_training_job(
            session=session,
            settings=settings,
            job_id=job_id,
            progress_callback=lambda progress, details=None: self.set_progress(
                job_id=job_id,
                progress_percent=progress,
                details_update=details,
            ),
        )
