"""Worker and scheduler runtime bootstrap tests."""

from __future__ import annotations

from rl_trade_common.settings import Settings
from rl_trade_worker.celery_app import create_celery_app
from rl_trade_worker.runtime import build_scheduler_argv, build_worker_argv, parse_worker_queue_names


def test_parse_worker_queue_names_deduplicates_and_preserves_order() -> None:
    assert parse_worker_queue_names("ingestion, maintenance, ingestion") == ("ingestion", "maintenance")


def test_parse_worker_queue_names_rejects_unknown_queue_names() -> None:
    try:
        parse_worker_queue_names("ingestion,unknown")
    except ValueError as exc:
        assert str(exc) == "worker_queues contains unknown queue names: unknown"
    else:
        raise AssertionError("Expected queue validation failure.")


def test_worker_and_scheduler_argv_respect_runtime_settings() -> None:
    settings = Settings(
        _env_file=None,
        worker_queues="trading,maintenance",
        worker_concurrency=3,
        worker_prefetch_multiplier=2,
        scheduler_max_interval_seconds=15,
        log_level="WARNING",
    )

    assert build_worker_argv(settings) == [
        "celery",
        "worker",
        "--loglevel",
        "warning",
        "--concurrency",
        "3",
        "--prefetch-multiplier",
        "2",
        "--queues",
        "trading,maintenance",
    ]
    assert build_scheduler_argv(settings) == [
        "celery",
        "beat",
        "--loglevel",
        "warning",
        "--max-interval",
        "15",
    ]


def test_celery_app_registers_maintenance_heartbeat_schedule(monkeypatch) -> None:
    monkeypatch.setattr(
        "rl_trade_worker.celery_app.get_settings",
        lambda: Settings(_env_file=None, scheduler_heartbeat_interval_seconds=120),
    )

    celery_app = create_celery_app()
    heartbeat = celery_app.conf.beat_schedule["worker-heartbeat"]

    assert heartbeat["task"] == "system.ping"
    assert heartbeat["schedule"] == 120.0
    assert heartbeat["options"]["queue"] == "maintenance"
