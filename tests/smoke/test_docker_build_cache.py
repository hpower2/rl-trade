"""Smoke coverage for Docker build cache layering."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_python_dockerfile_uses_dependency_cache_mounts_and_split_layers() -> None:
    dockerfile = _read_text("docker/python.Dockerfile")

    assert "# syntax=docker/dockerfile:1.7" in dockerfile
    assert "--mount=type=cache,target=/root/.cache/pip" in dockerfile
    assert "python -m pip install -r /tmp/requirements-runtime.txt" in dockerfile
    assert "python -m pip install --no-deps -e ." in dockerfile
    assert dockerfile.index("python -m pip install -r /tmp/requirements-runtime.txt") < dockerfile.index("COPY apps /app/apps")


def test_frontend_dockerfile_uses_npm_cache_mount_and_ci() -> None:
    dockerfile = _read_text("docker/frontend.Dockerfile")

    assert "# syntax=docker/dockerfile:1.7" in dockerfile
    assert "--mount=type=cache,target=/root/.npm" in dockerfile
    assert "npm ci --cache /root/.npm" in dockerfile


def test_makefile_enables_buildkit_for_compose_build() -> None:
    makefile = _read_text("Makefile")

    assert "DOCKER_BUILDKIT ?= 1" in makefile
    assert "DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build -t rl-trade-python:local -f docker/python.Dockerfile ." in makefile
    assert "DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build -t rl-trade-frontend:latest -f docker/frontend.Dockerfile ." in makefile
