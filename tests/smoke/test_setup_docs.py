"""Smoke checks for root setup documentation and env coverage."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def _read_env_keys() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _ = stripped.split("=", 1)
        keys.add(key)
    return keys


def test_env_example_covers_critical_runtime_and_safety_variables() -> None:
    keys = _read_env_keys()

    assert {
        "APP_ENV",
        "LOG_LEVEL",
        "API_AUTH_MODE",
        "API_AUTH_TOKEN",
        "DATABASE_URL",
        "REDIS_URL",
        "CPU_WORKER_QUEUES",
        "TRAINING_WORKER_QUEUES",
        "SCHEDULER_HEARTBEAT_INTERVAL_SECONDS",
        "ARTIFACTS_ROOT_DIR",
        "MT5_TERMINAL_PATH",
        "PAPER_TRADING_ONLY",
        "ALLOW_LIVE_TRADING",
        "MODEL_APPROVAL_MIN_CONFIDENCE",
        "MODEL_APPROVAL_MIN_RISK_REWARD",
        "POSTGRES_HOST_PORT",
        "REDIS_HOST_PORT",
        "API_HOST_PORT",
        "FRONTEND_HOST_PORT",
        "TRAINING_WORKER_REQUIRE_CUDA",
        "TRAINING_WORKER_NVIDIA_VISIBLE_DEVICES",
        "TRAINING_WORKER_GPUS",
    } <= keys


def test_readme_documents_environment_variables_and_troubleshooting() -> None:
    readme_text = README.read_text(encoding="utf-8")

    assert "## Environment Variables" in readme_text
    assert "## Troubleshooting" in readme_text
    assert "CPU_WORKER_QUEUES" in readme_text
    assert "TRAINING_WORKER_QUEUES" in readme_text
    assert "PAPER_TRADING_ONLY" in readme_text
    assert "ALLOW_LIVE_TRADING" in readme_text
    assert "make validate-compose-gpu-host" in readme_text
    assert "make validate-compose-gpu-runtime" in readme_text
