"""Shared task base classes for tracked background jobs."""

from __future__ import annotations

import logging
from typing import Any

from celery import Task
from celery.utils.log import get_task_logger

from rl_trade_data import (
    JobKind,
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
        self._run_status_update(
            "mark running",
            task_id,
            lambda: self._with_session(
                lambda session: mark_job_running(session, job_kind=self.job_kind, job_id=job_id)
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
            self._run_status_update(
                "mark succeeded",
                task_id,
                lambda: self._with_session(
                    lambda session: mark_job_succeeded(session, job_kind=self.job_kind, job_id=job_id)
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
            self._run_status_update(
                "mark retry",
                task_id,
                lambda: self._with_session(
                    lambda session: mark_job_retry(
                        session,
                        job_kind=self.job_kind,
                        job_id=job_id,
                        retry_count=retry_count,
                        reason=str(exc),
                    )
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
            self._run_status_update(
                "mark failed",
                task_id,
                lambda: self._with_session(
                    lambda session: mark_job_failed(
                        session,
                        job_kind=self.job_kind,
                        job_id=job_id,
                        error_message=str(exc),
                    )
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
        self._run_status_update(
            "update progress",
            getattr(self.request, "id", "unknown"),
            lambda: self._with_session(
                lambda session: update_job_progress(
                    session,
                    job_kind=self.job_kind,
                    job_id=job_id,
                    progress_percent=progress_percent,
                    details_update=details_update,
                )
            ),
        )

    def _extract_job_id(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
        job_id = kwargs.get("job_id")
        if job_id is None and args:
            job_id = args[0]
        if isinstance(job_id, bool) or not isinstance(job_id, int):
            return None
        return job_id

    def _with_session(self, callback: Any) -> None:
        with session_scope(get_session_factory()) as session:
            callback(session)

    def _run_status_update(self, action: str, task_id: str, callback: Any) -> None:
        try:
            callback()
        except Exception:
            logger.exception(
                "Unable to %s for tracked task.",
                action,
                extra={"task_id": task_id, "task_name": self.name},
            )
