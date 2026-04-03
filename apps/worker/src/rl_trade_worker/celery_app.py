"""Celery application bootstrap for background workers."""

from celery import Celery

from rl_trade_common import get_settings
from rl_trade_worker.queues import MAINTENANCE_QUEUE, TASK_QUEUES, TASK_ROUTES
from rl_trade_worker.schedule import build_beat_schedule


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "rl_trade_worker",
        broker=settings.effective_celery_broker_url,
        backend=settings.effective_celery_result_backend,
        include=["rl_trade_worker.tasks"],
    )
    app.conf.update(
        accept_content=["json"],
        enable_utc=True,
        result_serializer="json",
        task_create_missing_queues=False,
        task_default_queue=MAINTENANCE_QUEUE,
        task_queues=TASK_QUEUES,
        task_routes=TASK_ROUTES,
        task_serializer="json",
        timezone="UTC",
        beat_schedule=build_beat_schedule(settings),
    )
    return app


celery_app = create_celery_app()
