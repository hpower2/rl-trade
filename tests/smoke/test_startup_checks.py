"""Unit tests for Docker startup check routing."""

from __future__ import annotations

import importlib.util
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
