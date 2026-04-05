"""Smoke checks for the repo's GitHub Actions smoke workflows."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
BACKEND_SMOKE_WORKFLOW = WORKFLOWS_DIR / "backend-smoke.yml"
FRONTEND_SMOKE_WORKFLOW = WORKFLOWS_DIR / "frontend-playwright-smoke.yml"


def test_backend_smoke_workflow_runs_expected_backend_validation_lane() -> None:
    workflow_text = BACKEND_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "name: Backend Smoke" in workflow_text
    assert "pull_request:" in workflow_text
    assert "push:" in workflow_text
    assert "branches:" in workflow_text
    assert "- main" in workflow_text
    assert "uses: actions/setup-python@v5" in workflow_text
    assert 'python-version: "3.12"' in workflow_text
    assert "python -m pip install --upgrade pip && python -m pip install -e .[dev]" in workflow_text
    assert "python -m pytest tests/smoke/test_setup_docs.py tests/api/test_health.py tests/smoke/test_core_workflow_dry_run.py -q" in workflow_text
    assert "make validate-hardening-backend" in workflow_text
    assert "make validate-core-smoke" in workflow_text


def test_frontend_smoke_workflow_runs_expected_playwright_lane() -> None:
    workflow_text = FRONTEND_SMOKE_WORKFLOW.read_text(encoding="utf-8")

    assert "name: Frontend Playwright Smoke" in workflow_text
    assert "pull_request:" in workflow_text
    assert "push:" in workflow_text
    assert "branches:" in workflow_text
    assert "- main" in workflow_text
    assert "uses: actions/setup-node@v4" in workflow_text
    assert "node-version: 20" in workflow_text
    assert "run: npm ci" in workflow_text
    assert "run: npx playwright install --with-deps chromium" in workflow_text
    assert "working-directory: apps/frontend" in workflow_text
    assert "run: npm run frontend:test" in workflow_text
    assert "run: npm run frontend:test:e2e" in workflow_text
    assert "uses: actions/upload-artifact@v4" in workflow_text
    assert "path: apps/frontend/output/playwright" in workflow_text
