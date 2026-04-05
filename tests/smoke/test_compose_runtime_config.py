"""Smoke tests for Docker Compose runtime topology."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _normalize_ports(raw_ports: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for entry in raw_ports if isinstance(raw_ports, list) else []:
        if isinstance(entry, dict):
            normalized.append(entry)
            continue
        if isinstance(entry, str) and ":" in entry:
            published, target = entry.split(":", 1)
            normalized.append({"published": published, "target": int(target)})
    return normalized


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


def test_compose_exposes_frontend_only_and_keeps_api_internal() -> None:
    config = _load_compose_config()
    services = config["services"]

    api = services["api"]
    frontend = services["frontend"]

    assert "ports" not in api
    assert api["expose"] == ["8000"]

    frontend_ports = _normalize_ports(frontend["ports"])
    assert frontend_ports == [
        {
            "mode": "ingress",
            "target": 80,
            "published": "4173",
            "protocol": "tcp",
        }
    ]


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
