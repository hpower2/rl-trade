"""Smoke checks for the clean setup validator tool."""

from __future__ import annotations

from rl_trade_api.tools import validate_clean_setup


def test_clean_setup_validator_dry_run_lists_documented_commands(capsys) -> None:
    exit_code = validate_clean_setup.run(["--dry-run"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "cp .env.example .env" in captured.out
    assert "python3 -m venv .venv" in captured.out
    assert "python -m pip install -e .[dev]" in captured.out
    assert "make validate-backend" in captured.out
    assert "npm install" in captured.out
    assert "npx playwright install --with-deps chromium" in captured.out
    assert "npm run frontend:test" in captured.out
