"""Smoke coverage for the manual core workflow dry-run command."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_core_workflow_dry_run_command_completes() -> None:
    python_bin = REPO_ROOT / ".venv" / "bin" / "python"
    assert python_bin.exists(), "expected repo virtualenv at .venv/bin/python"

    completed = subprocess.run(
        [str(python_bin), "-m", "rl_trade_api.tools.core_workflow_dry_run"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "validated symbol=EURUSD" in completed.stdout
    assert "ingestion status=succeeded" in completed.stdout
    assert "preprocessing status=succeeded" in completed.stdout
    assert "training status=succeeded" in completed.stdout
    assert "evaluation approved=True" in completed.stdout
    assert "signal status=accepted" in completed.stdout
    assert "order status=submitted" in completed.stdout
    assert "positions count=1" in completed.stdout
    assert "Core workflow dry run completed." in completed.stdout
