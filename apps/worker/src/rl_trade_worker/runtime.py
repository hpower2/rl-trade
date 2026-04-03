"""Runtime argument builders for Celery worker and scheduler entry points."""

from __future__ import annotations

from rl_trade_common import Settings
from rl_trade_worker.queues import ALL_QUEUE_NAMES


def parse_worker_queue_names(queue_names: str) -> tuple[str, ...]:
    parsed_names = tuple(dict.fromkeys(name.strip() for name in queue_names.split(",") if name.strip()))
    if not parsed_names:
        raise ValueError("worker_queues must include at least one queue name.")

    unknown_names = tuple(name for name in parsed_names if name not in ALL_QUEUE_NAMES)
    if unknown_names:
        raise ValueError(f"worker_queues contains unknown queue names: {', '.join(unknown_names)}")

    return parsed_names


def build_worker_argv(settings: Settings) -> list[str]:
    queue_names = parse_worker_queue_names(settings.worker_queues)
    return [
        "celery",
        "worker",
        "--loglevel",
        settings.log_level.lower(),
        "--concurrency",
        str(settings.worker_concurrency),
        "--prefetch-multiplier",
        str(settings.worker_prefetch_multiplier),
        "--queues",
        ",".join(queue_names),
    ]


def build_scheduler_argv(settings: Settings) -> list[str]:
    return [
        "celery",
        "beat",
        "--loglevel",
        settings.log_level.lower(),
        "--max-interval",
        str(settings.scheduler_max_interval_seconds),
    ]
