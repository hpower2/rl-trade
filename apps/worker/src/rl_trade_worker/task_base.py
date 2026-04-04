"""Shared task base classes for tracked background jobs."""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Any, Protocol, TypeVar

from celery import Task
from celery.utils.log import get_task_logger

from rl_trade_data import (
    IngestionJob,
    JobKind,
    PreprocessingJob,
    RLTrainingJob,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    get_session_factory,
    mark_job_failed,
    mark_job_retry,
    mark_job_running,
    mark_job_succeeded,
    session_scope,
    update_job_progress,
)

logger = get_task_logger(__name__)
event_logger = logging.getLogger("rl_trade_worker.task_events")
T = TypeVar("T")


class EventPublisher(Protocol):
    def publish_event(
        self,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        occurred_at: Any | None = None,
    ) -> Any: ...


def get_event_publisher() -> EventPublisher | None:
    return None


class TransientTaskError(RuntimeError):
    """Signals a retryable background task failure."""


class TrackedTask(Task):
    abstract = True
    autoretry_for = (TransientTaskError,)
    retry_backoff = True
    retry_jitter = False
    retry_kwargs = {"max_retries": 3}
    job_kind: JobKind | None = None

    def before_start(self, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        job_id = self._extract_job_id(args, kwargs)
        if self.job_kind is None or job_id is None:
            return
        self._run_job_update(
            "mark running",
            task_id,
            lambda session: mark_job_running(
                session,
                job_kind=self.job_kind,
                job_id=job_id,
            ),
        )

    def on_success(
        self,
        retval: Any,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        job_id = self._extract_job_id(args, kwargs)
        if self.job_kind is not None and job_id is not None:
            self._run_job_update(
                "mark succeeded",
                task_id,
                lambda session: mark_job_succeeded(
                    session,
                    job_kind=self.job_kind,
                    job_id=job_id,
                ),
            )
        logger.info(
            "Tracked task %s succeeded for job %s.",
            self.name,
            job_id,
            extra={"task_id": task_id, "task_name": self.name, "job_id": job_id},
        )
        event_logger.info("Tracked task %s succeeded for job %s.", self.name, job_id)

    def on_retry(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        job_id = self._extract_job_id(args, kwargs)
        retry_count = getattr(self.request, "retries", 0) + 1
        if self.job_kind is not None and job_id is not None:
            self._run_job_update(
                "mark retry",
                task_id,
                lambda session: mark_job_retry(
                    session,
                    job_kind=self.job_kind,
                    job_id=job_id,
                    retry_count=retry_count,
                    reason=str(exc),
                ),
            )
        logger.warning(
            "Tracked task %s scheduled retry %s for job %s: %s",
            self.name,
            retry_count,
            job_id,
            exc,
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "job_id": job_id,
                "retry_count": retry_count,
            },
        )
        event_logger.warning(
            "Tracked task %s scheduled retry %s for job %s: %s",
            self.name,
            retry_count,
            job_id,
            exc,
        )

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        job_id = self._extract_job_id(args, kwargs)
        if self.job_kind is not None and job_id is not None:
            self._run_job_update(
                "mark failed",
                task_id,
                lambda session: mark_job_failed(
                    session,
                    job_kind=self.job_kind,
                    job_id=job_id,
                    error_message=str(exc),
                ),
            )
        logger.exception(
            "Tracked task %s failed for job %s: %s",
            self.name,
            job_id,
            exc,
            exc_info=exc,
            extra={"task_id": task_id, "task_name": self.name, "job_id": job_id},
        )
        event_logger.exception(
            "Tracked task %s failed for job %s: %s",
            self.name,
            job_id,
            exc,
            exc_info=exc,
        )

    def set_progress(
        self,
        *,
        job_id: int,
        progress_percent: int,
        details_update: dict[str, Any] | None = None,
    ) -> None:
        if self.job_kind is None:
            return
        self._run_job_update(
            "update progress",
            getattr(self.request, "id", "unknown"),
            lambda session: update_job_progress(
                session,
                job_kind=self.job_kind,
                job_id=job_id,
                progress_percent=progress_percent,
                details_update=details_update,
            ),
        )

    def _extract_job_id(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
        job_id = kwargs.get("job_id")
        if job_id is None and args:
            job_id = args[0]
        if isinstance(job_id, bool) or not isinstance(job_id, int):
            return None
        return job_id

    def _with_session(self, callback: Any) -> Any:
        with session_scope(get_session_factory()) as session:
            return callback(session)

    def _run_status_update(self, action: str, task_id: str, callback: Any) -> T | None:
        try:
            return callback()
        except Exception:
            logger.exception(
                "Unable to %s for tracked task.",
                action,
                extra={"task_id": task_id, "task_name": self.name},
            )
            return None

    def _run_job_update(
        self,
        action: str,
        task_id: str,
        callback: Any,
    ) -> None:
        self._run_status_update(
            action,
            task_id,
            lambda: self._with_session(lambda session: self._apply_job_update(session=session, callback=callback)),
        )

    def _apply_job_update(self, *, session: Any, callback: Any) -> Any:
        job = callback(session)
        self._publish_job_event(session=session, job=job)
        return job

    def _publish_job_event(self, *, session: Any, job: Any) -> None:
        publisher = get_event_publisher()
        if publisher is None or self.job_kind is None or job is None:
            return

        event = _build_job_event(session=session, job_kind=self.job_kind, job=job)
        if event is None:
            return

        try:
            publisher.publish_event(
                event_type=event["event_type"],
                entity_type=event["entity_type"],
                entity_id=event["entity_id"],
                payload=event["payload"],
                occurred_at=event["occurred_at"],
            )
        except Exception:
            logger.exception(
                "Unable to publish worker event for tracked task.",
                extra={"task_name": self.name, "job_kind": self.job_kind.value, "job_id": getattr(job, "id", None)},
            )


def _build_job_event(*, session: Any, job_kind: JobKind, job: Any) -> dict[str, Any] | None:
    occurred_at = getattr(job, "updated_at", None)
    if occurred_at is not None and getattr(occurred_at, "tzinfo", None) is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)

    if job_kind is JobKind.INGESTION and isinstance(job, IngestionJob):
        symbol = session.get(Symbol, job.symbol_id)
        if symbol is None:
            return None
        return {
            "event_type": "ingestion_progress",
            "entity_type": "ingestion_job",
            "entity_id": str(job.id),
            "occurred_at": occurred_at,
            "payload": {
                "job_id": job.id,
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "status": job.status.value,
                "progress_percent": job.progress_percent,
                "sync_mode": job.sync_mode,
                "requested_timeframes": list(job.requested_timeframes),
                "source_provider": job.source_provider,
                "candles_requested": job.candles_requested,
                "candles_written": job.candles_written,
                "last_successful_candle_time": (
                    job.last_successful_candle_time.isoformat() if job.last_successful_candle_time is not None else None
                ),
                "error_message": job.error_message,
                "details": dict(job.details or {}),
                "source": "worker_task",
            },
        }

    if job_kind is JobKind.PREPROCESSING and isinstance(job, PreprocessingJob):
        symbol = session.get(Symbol, job.symbol_id)
        if symbol is None:
            return None
        details = dict(job.details or {})
        return {
            "event_type": "preprocessing_progress",
            "entity_type": "preprocessing_job",
            "entity_id": str(job.id),
            "occurred_at": occurred_at,
            "payload": {
                "job_id": job.id,
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "status": job.status.value,
                "progress_percent": job.progress_percent,
                "requested_timeframes": list(job.requested_timeframes),
                "primary_timeframe": details.get("primary_timeframe"),
                "feature_set_name": details.get("feature_set_name"),
                "feature_set_version": details.get("feature_set_version"),
                "dataset_version_id": job.dataset_version_id,
                "error_message": job.error_message,
                "details": details,
                "source": "worker_task",
            },
        }

    if job_kind is JobKind.SUPERVISED_TRAINING and isinstance(job, SupervisedTrainingJob):
        training_request = session.get(TrainingRequest, job.training_request_id)
        if training_request is None:
            return None
        symbol = session.get(Symbol, training_request.symbol_id)
        if symbol is None:
            return None
        return {
            "event_type": "training_progress",
            "entity_type": "supervised_training_job",
            "entity_id": str(job.id),
            "occurred_at": occurred_at,
            "payload": {
                "job_id": job.id,
                "training_request_id": training_request.id,
                "dataset_version_id": job.dataset_version_id,
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "algorithm": job.algorithm,
                "status": job.status.value,
                "progress_percent": job.progress_percent,
                "error_message": job.error_message,
                "metrics": dict(job.metrics or {}),
                "source": "worker_task",
            },
        }

    if job_kind is JobKind.RL_TRAINING and isinstance(job, RLTrainingJob):
        training_request = session.get(TrainingRequest, job.training_request_id)
        if training_request is None:
            return None
        symbol = session.get(Symbol, training_request.symbol_id)
        if symbol is None:
            return None
        return {
            "event_type": "training_progress",
            "entity_type": "rl_training_job",
            "entity_id": str(job.id),
            "occurred_at": occurred_at,
            "payload": {
                "job_id": job.id,
                "training_request_id": training_request.id,
                "dataset_version_id": job.dataset_version_id,
                "symbol_id": symbol.id,
                "symbol_code": symbol.code,
                "algorithm": job.algorithm,
                "environment_name": job.environment_name,
                "status": job.status.value,
                "progress_percent": job.progress_percent,
                "error_message": job.error_message,
                "metrics": dict(job.metrics or {}),
                "source": "worker_task",
            },
        }

    return None
