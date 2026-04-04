"""Smoke tests for the Compose runtime verification helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_verify_compose_module():
    module_path = Path(__file__).resolve().parents[2] / "docker" / "scripts" / "verify_compose_runtime.py"
    spec = importlib.util.spec_from_file_location("verify_compose_runtime_module", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_compose_ps_command_supports_multiple_compose_files() -> None:
    module = _load_verify_compose_module()

    command = module.build_compose_ps_command(
        compose_files=("compose.yaml", "docker/compose.gpu.yaml"),
        services=("api", "training_worker"),
    )

    assert command == [
        "docker",
        "compose",
        "-f",
        "compose.yaml",
        "-f",
        "docker/compose.gpu.yaml",
        "ps",
        "--all",
        "--format",
        "json",
        "api",
        "training_worker",
    ]


def test_parse_ps_payload_supports_json_array_and_ndjson() -> None:
    module = _load_verify_compose_module()

    array_rows = module.parse_ps_payload('[{"Service":"api","State":"running"}]')
    ndjson_rows = module.parse_ps_payload('{"Service":"api","State":"running"}\n{"Service":"worker","State":"running"}')

    assert array_rows == [{"Service": "api", "State": "running"}]
    assert ndjson_rows == [
        {"Service": "api", "State": "running"},
        {"Service": "worker", "State": "running"},
    ]


def test_inspect_runtime_rows_accepts_expected_service_states() -> None:
    module = _load_verify_compose_module()

    rows = [
        {"Service": "postgres", "State": "running", "Health": "healthy"},
        {"Service": "redis", "State": "running", "Health": "healthy"},
        {"Service": "migrate", "State": "exited", "ExitCode": 0},
        {"Service": "api", "State": "running", "Health": "healthy"},
        {"Service": "worker", "State": "running"},
        {"Service": "training_worker", "State": "running"},
        {"Service": "scheduler", "State": "running"},
        {"Service": "frontend", "State": "running", "Health": "healthy"},
    ]

    healthy, details = module.inspect_runtime_rows(rows)

    assert healthy is True
    assert details == [
        "postgres=running+healthy",
        "redis=running+healthy",
        "migrate=exited(0)",
        "api=running+healthy",
        "worker=running",
        "training_worker=running",
        "scheduler=running",
        "frontend=running+healthy",
    ]


def test_inspect_runtime_rows_reports_unhealthy_and_missing_services() -> None:
    module = _load_verify_compose_module()

    rows = [
        {"Service": "postgres", "State": "running", "Health": "starting"},
        {"Service": "redis", "State": "running", "Health": "healthy"},
        {"Service": "migrate", "State": "exited", "ExitCode": 1},
        {"Service": "api", "State": "restarting", "Health": "unhealthy"},
    ]

    healthy, details = module.inspect_runtime_rows(rows)

    assert healthy is False
    assert details == [
        "postgres: expected running+healthy, got state=running health=starting",
        "migrate: expected exited with code 0, got state=exited exit_code=1",
        "api: expected running+healthy, got state=restarting health=unhealthy",
        "worker: missing from docker compose ps output",
        "training_worker: missing from docker compose ps output",
        "scheduler: missing from docker compose ps output",
        "frontend: missing from docker compose ps output",
    ]


def test_wait_for_runtime_validation_retries_until_services_are_ready() -> None:
    module = _load_verify_compose_module()

    attempts = iter(
        [
            [
                {"Service": "postgres", "State": "running", "Health": "starting"},
                {"Service": "redis", "State": "running", "Health": "healthy"},
            ],
            [
                {"Service": "postgres", "State": "running", "Health": "healthy"},
                {"Service": "redis", "State": "running", "Health": "healthy"},
                {"Service": "migrate", "State": "exited", "ExitCode": 0},
                {"Service": "api", "State": "running", "Health": "healthy"},
                {"Service": "worker", "State": "running"},
                {"Service": "training_worker", "State": "running"},
                {"Service": "scheduler", "State": "running"},
                {"Service": "frontend", "State": "running", "Health": "healthy"},
            ],
        ]
    )
    sleeps: list[float] = []

    healthy, details = module.wait_for_runtime_validation(
        lambda: next(attempts),
        max_attempts=2,
        retry_interval_seconds=0.25,
        sleep_fn=sleeps.append,
    )

    assert healthy is True
    assert details[-1] == "frontend=running+healthy"
    assert sleeps == [0.25]


def test_wait_for_runtime_validation_returns_last_attempt_details_on_timeout() -> None:
    module = _load_verify_compose_module()

    rows = [
        {"Service": "postgres", "State": "running", "Health": "starting"},
        {"Service": "redis", "State": "running", "Health": "healthy"},
    ]

    healthy, details = module.wait_for_runtime_validation(
        lambda: rows,
        max_attempts=2,
        retry_interval_seconds=0.5,
        sleep_fn=lambda _: None,
    )

    assert healthy is False
    assert details[0] == "attempt 2/2: postgres: expected running+healthy, got state=running health=starting"
