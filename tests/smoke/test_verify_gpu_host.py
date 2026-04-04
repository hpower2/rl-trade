"""Smoke tests for the GPU-host preflight helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_verify_gpu_host_module():
    module_path = Path(__file__).resolve().parents[2] / "docker" / "scripts" / "verify_gpu_host.py"
    spec = importlib.util.spec_from_file_location("verify_gpu_host_module", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_docker_info_payload_requires_json_object() -> None:
    module = _load_verify_gpu_host_module()

    info = module.parse_docker_info_payload('{"Runtimes":{"runc":{"path":"runc"}}}')

    assert info == {"Runtimes": {"runc": {"path": "runc"}}}


def test_inspect_gpu_host_info_accepts_nvidia_runtime() -> None:
    module = _load_verify_gpu_host_module()

    healthy, details = module.inspect_gpu_host_info(
        {
            "Runtimes": {"runc": {"path": "runc"}, "nvidia": {"path": "nvidia-container-runtime"}},
            "DefaultRuntime": "runc",
            "DriverStatus": [["NVIDIA Driver", "550.54.14"]],
        }
    )

    assert healthy is True
    assert details == [
        "nvidia runtime detected (available_runtimes=nvidia,runc)",
        "default_runtime=runc",
        "docker driver status references NVIDIA support",
    ]


def test_inspect_gpu_host_info_rejects_missing_nvidia_runtime() -> None:
    module = _load_verify_gpu_host_module()

    healthy, details = module.inspect_gpu_host_info(
        {
            "Runtimes": {"io.containerd.runc.v2": {}, "runc": {}},
            "DefaultRuntime": "runc",
        }
    )

    assert healthy is False
    assert details == [
        "Docker host does not advertise an 'nvidia' runtime. Install/configure the NVIDIA container runtime first."
    ]
