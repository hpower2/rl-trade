"""CLI bootstrap for the Celery beat scheduler service."""

import logging

from rl_trade_common import configure_logging, get_settings
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.runtime import build_scheduler_argv


def run() -> None:
    settings = get_settings()
    configure_logging(service_name="scheduler", settings=settings)
    argv = build_scheduler_argv(settings)

    logger = logging.getLogger("rl_trade_scheduler")
    logger.info(
        "Starting Celery beat scheduler.",
        extra={
            "heartbeat_interval_seconds": settings.scheduler_heartbeat_interval_seconds,
            "max_interval_seconds": settings.scheduler_max_interval_seconds,
        },
    )
    celery_app.start(argv)


if __name__ == "__main__":
    run()
