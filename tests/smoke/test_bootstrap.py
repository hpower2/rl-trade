"""Smoke tests for service bootstrap entry points."""

from __future__ import annotations

from fastapi.testclient import TestClient

from rl_trade_api.app import create_app
from rl_trade_worker.celery_app import create_celery_app
from rl_trade_worker.main import run as run_worker
from rl_trade_worker.scheduler import run as run_scheduler
from rl_trade_worker.tasks import ping


def test_api_root_endpoint_reports_bootstrap_state() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "api",
        "status": "bootstrapped",
        "environment": "local",
        "paper_trading_only": True,
    }


def test_worker_bootstrap_uses_expected_defaults() -> None:
    celery_app = create_celery_app()

    assert celery_app.main == "rl_trade_worker"
    assert celery_app.conf.enable_utc is True
    assert celery_app.conf.task_default_queue == "maintenance"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.timezone == "UTC"


def test_worker_ping_task_returns_ok_status() -> None:
    assert ping() == {"service": "worker", "status": "ok"}


def test_worker_cli_bootstrap_starts_celery_runtime(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("rl_trade_worker.main.configure_logging", lambda service_name, settings: None)
    monkeypatch.setattr("rl_trade_worker.main.get_settings", lambda: create_settings_for_runtime())
    monkeypatch.setattr("rl_trade_worker.main.celery_app.start", lambda argv: captured.setdefault("worker", argv))

    run_worker()

    assert captured["worker"] == [
        "celery",
        "worker",
        "--loglevel",
        "info",
        "--concurrency",
        "2",
        "--prefetch-multiplier",
        "1",
        "--queues",
        "ingestion,maintenance",
    ]


def test_scheduler_cli_bootstrap_starts_beat_runtime(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("rl_trade_worker.scheduler.configure_logging", lambda service_name, settings: None)
    monkeypatch.setattr("rl_trade_worker.scheduler.get_settings", lambda: create_settings_for_runtime())
    monkeypatch.setattr("rl_trade_worker.scheduler.celery_app.start", lambda argv: captured.setdefault("scheduler", argv))

    run_scheduler()

    assert captured["scheduler"] == [
        "celery",
        "beat",
        "--loglevel",
        "info",
        "--max-interval",
        "12",
    ]


def create_settings_for_runtime():
    from rl_trade_common.settings import Settings

    return Settings(
        _env_file=None,
        worker_queues="ingestion,maintenance",
        worker_concurrency=2,
        worker_prefetch_multiplier=1,
        scheduler_heartbeat_interval_seconds=45,
        scheduler_max_interval_seconds=12,
    )
