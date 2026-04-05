"""Smoke checks for root setup documentation and env coverage."""

from __future__ import annotations

import json
from importlib import util as importlib_util
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
SETUP_DOC = REPO_ROOT / "docs" / "setup.md"
PLANS = REPO_ROOT / "PLANS.md"
MAKEFILE = REPO_ROOT / "Makefile"
PACKAGE_JSON = REPO_ROOT / "package.json"


def _read_env_keys() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _ = stripped.split("=", 1)
        keys.add(key)
    return keys


def _read_make_targets() -> set[str]:
    targets: set[str] = set()
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):(?:\s|$)", line)
        if match is not None:
            targets.add(match.group(1))
    return targets


def _read_package_scripts() -> set[str]:
    package_data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    return set(package_data.get("scripts", {}))


def _documented_make_targets(*texts: str) -> set[str]:
    return {match.group(1) for text in texts for match in re.finditer(r"(?<![\w-])make ([A-Za-z0-9:-]+)", text)}


def _documented_npm_scripts(*texts: str) -> set[str]:
    return {match.group(1) for text in texts for match in re.finditer(r"npm run ([A-Za-z0-9:-]+)", text)}


def _documented_repo_python_modules(*texts: str) -> set[str]:
    pattern = r"python -m ((?:rl_trade_[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*))"
    return {match.group(1) for text in texts for match in re.finditer(pattern, text)}


def test_env_example_covers_critical_runtime_and_safety_variables() -> None:
    keys = _read_env_keys()

    assert {
        "APP_ENV",
        "LOG_LEVEL",
        "API_AUTH_MODE",
        "API_AUTH_TOKEN",
        "DATABASE_URL",
        "REDIS_URL",
        "CPU_WORKER_QUEUES",
        "TRAINING_WORKER_QUEUES",
        "SCHEDULER_HEARTBEAT_INTERVAL_SECONDS",
        "ARTIFACTS_ROOT_DIR",
        "MT5_TERMINAL_PATH",
        "PAPER_TRADING_ONLY",
        "ALLOW_LIVE_TRADING",
        "MODEL_APPROVAL_MIN_CONFIDENCE",
        "MODEL_APPROVAL_MIN_RISK_REWARD",
        "POSTGRES_HOST_PORT",
        "REDIS_HOST_PORT",
        "API_HOST_PORT",
        "FRONTEND_HOST_PORT",
        "TRAINING_WORKER_REQUIRE_CUDA",
        "TRAINING_WORKER_NVIDIA_VISIBLE_DEVICES",
        "TRAINING_WORKER_GPUS",
    } <= keys


def test_readme_documents_environment_variables_and_troubleshooting() -> None:
    readme_text = README.read_text(encoding="utf-8")

    assert "## Safety Guarantees" in readme_text
    assert "Demo trading only" in readme_text
    assert "live MT5 accounts are blocked in backend code" in readme_text
    assert "a symbol cannot be paper traded unless it has an approved model" in readme_text
    assert "confidence must be at least `70%`" in readme_text
    assert "risk-to-reward must be at least `2.0`" in readme_text
    assert "run through workers rather than API request handlers" in readme_text
    assert "## Environment Variables" in readme_text
    assert "## Troubleshooting" in readme_text
    assert "CPU_WORKER_QUEUES" in readme_text
    assert "TRAINING_WORKER_QUEUES" in readme_text
    assert "PAPER_TRADING_ONLY" in readme_text
    assert "ALLOW_LIVE_TRADING" in readme_text
    assert "make validate-compose-gpu-host" in readme_text
    assert "make validate-compose-gpu-runtime" in readme_text


def test_setup_runbook_covers_clean_install_and_smoke_commands() -> None:
    setup_text = SETUP_DOC.read_text(encoding="utf-8")

    assert "# Local Setup Runbook" in setup_text
    assert "cp .env.example .env" in setup_text
    assert "PAPER_TRADING_ONLY=true" in setup_text
    assert "ALLOW_LIVE_TRADING=false" in setup_text
    assert "make run-api" in setup_text
    assert "make run-worker" in setup_text
    assert "make run-scheduler" in setup_text
    assert "make run-frontend" in setup_text
    assert "docker compose config" in setup_text
    assert "make compose-build" in setup_text
    assert "make validate-compose-runtime" in setup_text
    assert "make validate-core-smoke" in setup_text
    assert "make validate-clean-setup" in setup_text
    assert "make validate-milestone15" in setup_text
    assert "python -m rl_trade_api.tools.paper_trading_dry_run" in setup_text
    assert "python -m rl_trade_api.tools.websocket_event_dry_run" in setup_text
    assert "npm run frontend:test:e2e" in setup_text


def test_documented_commands_map_to_real_repo_tooling() -> None:
    readme_text = README.read_text(encoding="utf-8")
    setup_text = SETUP_DOC.read_text(encoding="utf-8")

    documented_make_targets = _documented_make_targets(readme_text, setup_text)
    documented_npm_scripts = _documented_npm_scripts(readme_text, setup_text)
    documented_python_modules = _documented_repo_python_modules(readme_text, setup_text)

    assert documented_make_targets <= _read_make_targets()
    assert documented_npm_scripts <= _read_package_scripts()

    unresolved_modules = sorted(
        module_name
        for module_name in documented_python_modules
        if importlib_util.find_spec(module_name) is None
    )
    assert unresolved_modules == []


def test_plans_validation_commands_section_uses_real_repo_commands() -> None:
    plans_text = PLANS.read_text(encoding="utf-8")

    assert "These commands reflect the current repo tooling for the Milestone 15 validation surface." in plans_text
    assert "placeholders and should be updated" not in plans_text
    assert "`make test-backend`" in plans_text
    assert "`make validate-core-smoke`" in plans_text
    assert "`make validate-clean-setup`" in plans_text
    assert "`make validate-hardening-backend`" in plans_text
    assert "`make validate-milestone15`" in plans_text
    assert "`npm run frontend:test:e2e`" in plans_text
    assert "`make validate-compose`" in plans_text
    assert "`make compose-up`" in plans_text
