"""Smoke tests for Docker Compose runtime topology."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_compose_config(*extra_files: str) -> dict[str, object]:
    if shutil.which("docker") is None:
        pytest.skip("docker is required for Compose config validation")

    command = ["docker", "compose", "-f", "compose.yaml"]
    for file_path in extra_files:
        command.extend(["-f", file_path])
    command.extend(["config", "--format", "json"])

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_base_compose_isolates_cpu_and_training_workers() -> None:
    config = _load_compose_config()
    services = config["services"]

    worker = services["worker"]
    training_worker = services["training_worker"]

    assert worker["environment"]["WORKER_QUEUES"] == "ingestion,preprocessing,evaluation,trading,maintenance"
    assert worker["environment"]["REQUIRE_CUDA"] == "false"
    assert training_worker["environment"]["WORKER_QUEUES"] == "supervised_training,rl_training"
    assert training_worker["environment"]["REQUIRE_CUDA"] == "false"
    assert training_worker["command"][2] == "training_worker"


def test_gpu_override_targets_only_training_worker() -> None:
    config = _load_compose_config("docker/compose.gpu.yaml")
    services = config["services"]

    worker = services["worker"]
    training_worker = services["training_worker"]

    assert "gpus" not in worker
    assert worker["environment"]["REQUIRE_CUDA"] == "false"
    assert training_worker["environment"]["REQUIRE_CUDA"] == "true"
    assert training_worker["environment"]["NVIDIA_VISIBLE_DEVICES"] == "all"
    assert training_worker["gpus"] == [{"count": -1}]
