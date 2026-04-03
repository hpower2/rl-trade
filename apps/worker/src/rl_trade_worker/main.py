"""CLI bootstrap for the worker service."""

import logging

from rl_trade_common import configure_logging, get_settings
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.runtime import build_worker_argv, parse_worker_queue_names


def run() -> None:
    settings = get_settings()
    configure_logging(service_name="worker", settings=settings)
    queue_names = parse_worker_queue_names(settings.worker_queues)
    argv = build_worker_argv(settings)

    logger = logging.getLogger("rl_trade_worker")
    logger.info(
        "Starting Celery worker runtime.",
        extra={
            "queues": list(queue_names),
            "concurrency": settings.worker_concurrency,
            "prefetch_multiplier": settings.worker_prefetch_multiplier,
        },
    )
    celery_app.start(argv)


if __name__ == "__main__":
    run()
