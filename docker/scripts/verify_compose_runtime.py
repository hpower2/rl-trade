"""Verify expected Docker Compose runtime states for the local stack."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SERVICE_STATES = {
    "postgres": "healthy",
    "redis": "healthy",
    "migrate": "exited_zero",
    "api": "healthy",
    "worker": "running",
    "training_worker": "running",
    "scheduler": "running",
    "frontend": "healthy",
}

FetchRowsFn = Callable[[], list[dict[str, Any]]]


def build_compose_ps_command(*, compose_files: tuple[str, ...], services: tuple[str, ...]) -> list[str]:
    command = ["docker", "compose"]
    for compose_file in compose_files:
        command.extend(["-f", compose_file])
    command.extend(["ps", "--all", "--format", "json"])
    command.extend(services)
    return command


def parse_ps_payload(payload: str) -> list[dict[str, Any]]:
    normalized = payload.strip()
    if not normalized:
        return []

    try:
        decoded = json.loads(normalized)
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in normalized.splitlines() if line.strip()]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("Compose ps payload must decode to object rows.")
        return rows

    if isinstance(decoded, list):
        if not all(isinstance(row, dict) for row in decoded):
            raise ValueError("Compose ps payload array must contain object rows.")
        return decoded
    if isinstance(decoded, dict):
        return [decoded]

    raise ValueError("Compose ps payload must decode to an object or array of objects.")


def _get_field(row: dict[str, Any], *candidate_names: str) -> Any:
    lowered = {key.lower(): value for key, value in row.items()}
    for candidate in candidate_names:
        if candidate in row:
            return row[candidate]
        lowered_name = candidate.lower()
        if lowered_name in lowered:
            return lowered[lowered_name]
    return None


def _get_service_name(row: dict[str, Any]) -> str:
    service_name = _get_field(row, "Service", "service")
    if isinstance(service_name, str) and service_name.strip():
        return service_name.strip()
    return ""


def _get_state(row: dict[str, Any]) -> str:
    value = _get_field(row, "State", "state")
    return str(value or "").strip().lower()


def _get_health(row: dict[str, Any]) -> str:
    explicit = str(_get_field(row, "Health", "health") or "").strip().lower()
    if explicit:
        return explicit

    status = str(_get_field(row, "Status", "status") or "").strip().lower()
    if "(healthy)" in status:
        return "healthy"
    if "(unhealthy)" in status:
        return "unhealthy"
    if "(starting)" in status:
        return "starting"
    return ""


def _get_exit_code(row: dict[str, Any]) -> int | None:
    raw = _get_field(row, "ExitCode", "exitCode", "exit_code")
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def inspect_runtime_rows(
    rows: list[dict[str, Any]],
    *,
    expected_service_states: dict[str, str] | None = None,
) -> tuple[bool, list[str]]:
    expectations = expected_service_states or EXPECTED_SERVICE_STATES
    indexed_rows = {_get_service_name(row): row for row in rows if _get_service_name(row)}

    problems: list[str] = []
    summaries: list[str] = []

    for service_name, expected_state in expectations.items():
        row = indexed_rows.get(service_name)
        if row is None:
            problems.append(f"{service_name}: missing from docker compose ps output")
            continue

        state = _get_state(row)
        health = _get_health(row)
        exit_code = _get_exit_code(row)

        if expected_state == "healthy":
            if state != "running" or health != "healthy":
                problems.append(
                    f"{service_name}: expected running+healthy, got state={state or 'unknown'} health={health or 'unknown'}"
                )
                continue
            summaries.append(f"{service_name}=running+healthy")
            continue

        if expected_state == "running":
            if state != "running":
                problems.append(f"{service_name}: expected running, got state={state or 'unknown'}")
                continue
            summaries.append(f"{service_name}=running")
            continue

        if expected_state == "exited_zero":
            if state != "exited" or exit_code != 0:
                reported_exit = "unknown" if exit_code is None else str(exit_code)
                problems.append(
                    f"{service_name}: expected exited with code 0, got state={state or 'unknown'} exit_code={reported_exit}"
                )
                continue
            summaries.append(f"{service_name}=exited(0)")
            continue

        problems.append(f"{service_name}: unsupported expected state {expected_state}")

    return not problems, summaries if not problems else problems


def wait_for_runtime_validation(
    fetch_rows: FetchRowsFn,
    *,
    expected_service_states: dict[str, str] | None = None,
    max_attempts: int,
    retry_interval_seconds: float,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[bool, list[str]]:
    last_details: list[str] = ["Compose runtime validation did not run."]

    for attempt in range(1, max_attempts + 1):
        healthy, details = inspect_runtime_rows(
            fetch_rows(),
            expected_service_states=expected_service_states,
        )
        if healthy:
            return True, details

        last_details = [f"attempt {attempt}/{max_attempts}: {detail}" for detail in details]
        if attempt != max_attempts:
            sleep_fn(retry_interval_seconds)

    return False, last_details


def load_ps_payload(
    *,
    compose_files: tuple[str, ...],
    services: tuple[str, ...],
    ps_file: Path | None,
) -> str:
    if ps_file is not None:
        return ps_file.read_text(encoding="utf-8")

    command = build_compose_ps_command(compose_files=compose_files, services=services)
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or "docker compose ps command failed")
    return completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compose-file",
        action="append",
        dest="compose_files",
        help="Compose file to include. Defaults to compose.yaml.",
    )
    parser.add_argument(
        "--service",
        action="append",
        dest="services",
        help="Service to inspect. Defaults to the full expected Milestone 14 runtime set.",
    )
    parser.add_argument("--ps-file", type=Path)
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--retry-interval-seconds", type=float, default=3.0)
    args = parser.parse_args()

    compose_files = tuple(args.compose_files or ("compose.yaml",))
    services = tuple(args.services or EXPECTED_SERVICE_STATES.keys())
    max_attempts = args.max_attempts or (1 if args.ps_file is not None else 20)

    def fetch_rows() -> list[dict[str, Any]]:
        payload = load_ps_payload(compose_files=compose_files, services=services, ps_file=args.ps_file)
        return parse_ps_payload(payload)

    healthy, details = wait_for_runtime_validation(
        fetch_rows,
        max_attempts=max_attempts,
        retry_interval_seconds=args.retry_interval_seconds,
    )
    if not healthy:
        raise SystemExit("Compose runtime validation failed:\n- " + "\n- ".join(details))

    print("Compose runtime validation passed: " + ", ".join(details))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
