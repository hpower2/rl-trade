"""Smoke tests for the GPU runtime verification helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_verify_gpu_module():
    module_path = Path(__file__).resolve().parents[2] / "docker" / "scripts" / "verify_training_worker_gpu.py"
    spec = importlib.util.spec_from_file_location("verify_training_worker_gpu_module", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_compose_logs_command_uses_gpu_override_by_default_shape() -> None:
    module = _load_verify_gpu_module()

    command = module.build_compose_logs_command(
        compose_files=("compose.yaml", "docker/compose.gpu.yaml"),
        service="training_worker",
        tail=300,
    )

    assert command == [
        "docker",
        "compose",
        "-f",
        "compose.yaml",
        "-f",
        "docker/compose.gpu.yaml",
        "logs",
        "--no-color",
        "--tail",
        "300",
        "training_worker",
    ]


def test_inspect_cuda_log_text_prefers_latest_success_event() -> None:
    module = _load_verify_gpu_module()

    log_text = """
training_worker-1  | 2026-04-04 WARNING [startup-checks] cuda check degraded: CUDA is unavailable; training will degrade to CPU mode
training_worker-1  | 2026-04-04 INFO [startup-checks] cuda check: CUDA available with 2 device(s) [visible_devices=0,1]: RTX 6000 Ada, RTX 4000 SFF Ada
""".strip()

    healthy, message = module.inspect_cuda_log_text(log_text)

    assert healthy is True
    assert "CUDA available with 2 device(s)" in message
    assert "visible_devices=0,1" in message


def test_inspect_cuda_log_text_reports_latest_failure_event() -> None:
    module = _load_verify_gpu_module()

    log_text = """
training_worker-1  | 2026-04-04 INFO [startup-checks] mt5 check degraded: credentials are not configured; MT5 features will remain unavailable
training_worker-1  | 2026-04-04 WARNING [startup-checks] cuda check degraded: CUDA is required but no device is available
""".strip()

    healthy, message = module.inspect_cuda_log_text(log_text)

    assert healthy is False
    assert "CUDA is required but no device is available" in message


def test_inspect_cuda_log_text_fails_when_no_cuda_line_exists() -> None:
    module = _load_verify_gpu_module()

    healthy, message = module.inspect_cuda_log_text("training_worker-1  | 2026-04-04 INFO boot ok")

    assert healthy is False
    assert message == "No CUDA readiness log line found in training_worker logs."


def test_wait_for_cuda_validation_retries_when_log_line_is_not_ready_yet() -> None:
    module = _load_verify_gpu_module()

    attempts = iter(
        [
            "training_worker-1  | 2026-04-04 INFO boot ok",
            (
                "training_worker-1  | 2026-04-04 INFO [startup-checks] cuda check: "
                "CUDA available with 1 device(s) [visible_devices=0]: RTX 6000 Ada"
            ),
        ]
    )
    sleeps: list[float] = []

    healthy, message = module.wait_for_cuda_validation(
        lambda: next(attempts),
        max_attempts=2,
        retry_interval_seconds=0.25,
        sleep_fn=sleeps.append,
    )

    assert healthy is True
    assert "CUDA available with 1 device(s)" in message
    assert sleeps == [0.25]


def test_wait_for_cuda_validation_fails_immediately_for_terminal_cuda_error() -> None:
    module = _load_verify_gpu_module()

    healthy, message = module.wait_for_cuda_validation(
        lambda: (
            "training_worker-1  | 2026-04-04 WARNING [startup-checks] cuda check degraded: "
            "CUDA is required but no device is available"
        ),
        max_attempts=3,
        retry_interval_seconds=0.25,
        sleep_fn=lambda _: None,
    )

    assert healthy is False
    assert message == "attempt 1/3: training_worker-1  | 2026-04-04 WARNING [startup-checks] cuda check degraded: CUDA is required but no device is available"
