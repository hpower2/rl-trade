"""Validate the documented clean setup flow in a temporary workspace."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
IGNORED_WORKSPACE_PATTERNS = (
    ".git",
    ".venv",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "playwright-report",
    "test-results",
    "dist",
    "build",
)


@dataclass(frozen=True)
class SetupStep:
    label: str
    display_command: str
    command: tuple[str, ...]


def _build_steps(*, workspace: Path) -> list[SetupStep]:
    workspace_python = workspace / ".venv" / "bin" / "python"
    return [
        SetupStep(
            label="prepare env file",
            display_command="cp .env.example .env",
            command=("cp", ".env.example", ".env"),
        ),
        SetupStep(
            label="create backend virtualenv",
            display_command="python3 -m venv .venv",
            command=(sys.executable, "-m", "venv", ".venv"),
        ),
        SetupStep(
            label="upgrade pip",
            display_command="python -m pip install --upgrade pip",
            command=(str(workspace_python), "-m", "pip", "install", "--upgrade", "pip"),
        ),
        SetupStep(
            label="install backend dependencies",
            display_command="python -m pip install -e .[dev]",
            command=(str(workspace_python), "-m", "pip", "install", "-e", ".[dev]"),
        ),
        SetupStep(
            label="validate backend bootstrap",
            display_command="make validate-backend",
            command=("make", "validate-backend"),
        ),
        SetupStep(
            label="install frontend dependencies",
            display_command="npm install",
            command=("npm", "install"),
        ),
        SetupStep(
            label="install playwright browser",
            display_command="npx playwright install --with-deps chromium",
            command=("npx", "playwright", "install", "--with-deps", "chromium"),
        ),
        SetupStep(
            label="validate frontend unit smoke",
            display_command="npm run frontend:test",
            command=("npm", "run", "frontend:test"),
        ),
    ]


def _copy_workspace(destination: Path) -> None:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(*IGNORED_WORKSPACE_PATTERNS),
        dirs_exist_ok=True,
    )


def _run_step(*, step: SetupStep, workspace: Path) -> None:
    print(f"{step.label}: {step.display_command}", flush=True)
    subprocess.run(step.command, cwd=workspace, check=True)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the README/docs clean setup flow in a temporary workspace."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the clean-setup plan without executing it.",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep the temporary workspace on disk after execution.",
    )
    args = parser.parse_args(argv)

    temp_dir = tempfile.TemporaryDirectory(prefix="rl-trade-clean-setup-")
    workspace = Path(temp_dir.name) / "workspace"
    _copy_workspace(workspace)

    print(f"temporary_workspace={workspace}", flush=True)
    steps = _build_steps(workspace=workspace)

    try:
        if args.dry_run:
            for step in steps:
                print(step.display_command, flush=True)
            return 0

        for step in steps:
            _run_step(step=step, workspace=workspace)
    except subprocess.CalledProcessError as exc:
        print(f"clean setup validation failed while running: {exc.cmd}", file=sys.stderr, flush=True)
        print(f"temporary_workspace={workspace}", file=sys.stderr, flush=True)
        return exc.returncode or 1
    finally:
        if args.keep_workspace:
            saved_workspace = workspace
            temp_dir.cleanup = lambda: None  # type: ignore[method-assign]
            print(f"kept_workspace={saved_workspace}", flush=True)
        else:
            temp_dir.cleanup()

    print("Clean setup validation completed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
