"""Unit tests for Docker startup check routing and CUDA reporting."""

from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace
from pathlib import Path


def _load_startup_checks_module():
    module_path = Path(__file__).resolve().parents[2] / "docker" / "scripts" / "startup_checks.py"
    spec = importlib.util.spec_from_file_location("startup_checks_module", module_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_startup_checks_route_cuda_only_to_training_worker() -> None:
    module = _load_startup_checks_module()

    assert module.REQUIRED_CHECKS["worker"] == ("database", "redis")
    assert module.REQUIRED_CHECKS["training_worker"] == ("database", "redis")
    assert module.OPTIONAL_CHECKS["worker"] == ("mt5",)
    assert module.OPTIONAL_CHECKS["training_worker"] == ("mt5", "cuda")
    assert module.OPTIONAL_CHECKS["api"] == ("mt5",)
    assert module.OPTIONAL_CHECKS["scheduler"] == ("mt5",)


def test_check_cuda_reports_visible_device_inventory(monkeypatch) -> None:
    module = _load_startup_checks_module()

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 2,
            get_device_name=lambda index: ("RTX 6000 Ada", "RTX 4000 SFF Ada")[index],
        )
    )

    monkeypatch.setenv("NVIDIA_VISIBLE_DEVICES", "0,1")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    healthy, message = module.check_cuda(require_cuda=True)

    assert healthy is True
    assert message == (
        "CUDA available with 2 device(s) "
        "[visible_devices=0,1]: RTX 6000 Ada, RTX 4000 SFF Ada"
    )


def test_check_cuda_uses_runtime_managed_label_for_void_visible_devices(monkeypatch) -> None:
    module = _load_startup_checks_module()

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 1,
            get_device_name=lambda index: ("NVIDIA GeForce GTX 1080 Ti",)[index],
        )
    )

    monkeypatch.setenv("NVIDIA_VISIBLE_DEVICES", "void")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    healthy, message = module.check_cuda(require_cuda=True)

    assert healthy is True
    assert message == (
        "CUDA available with 1 device(s) "
        "[visible_devices=runtime-managed]: NVIDIA GeForce GTX 1080 Ti"
    )


def test_check_cuda_fails_closed_when_required_but_unavailable(monkeypatch) -> None:
    module = _load_startup_checks_module()

    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: False,
        )
    )

    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    healthy, message = module.check_cuda(require_cuda=True)

    assert healthy is False
    assert message == "CUDA is required but no device is available"
