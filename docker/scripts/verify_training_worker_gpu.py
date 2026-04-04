"""Verify that the Compose training worker reached a CUDA-ready state."""

from __future__ import annotations

import argparse
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUCCESS_MARKER = "CUDA available with"
FAILURE_MARKERS = (
    "CUDA is unavailable; training will degrade to CPU mode",
    "CUDA is required but no device is available",
    "torch import failed while CUDA is required",
    "torch import failed; worker will stay CPU-only",
)

FetchLogTextFn = Callable[[], str]


def build_compose_logs_command(*, compose_files: tuple[str, ...], service: str, tail: int) -> list[str]:
    command = ["docker", "compose"]
    for compose_file in compose_files:
        command.extend(["-f", compose_file])
    command.extend(["logs", "--no-color", "--tail", str(tail), service])
    return command


def inspect_cuda_log_text(log_text: str) -> tuple[bool, str]:
    latest_event: tuple[int, bool, str] | None = None

    for line_number, raw_line in enumerate(log_text.splitlines()):
        line = raw_line.strip()
        if SUCCESS_MARKER in line:
            latest_event = (line_number, True, line)
            continue

        for marker in FAILURE_MARKERS:
            if marker in line:
                latest_event = (line_number, False, line)
                break

    if latest_event is None:
        return False, "No CUDA readiness log line found in training_worker logs."

    return latest_event[1], latest_event[2]


def is_retryable_cuda_failure(message: str) -> bool:
    return message == "No CUDA readiness log line found in training_worker logs."


def wait_for_cuda_validation(
    fetch_log_text: FetchLogTextFn,
    *,
    max_attempts: int,
    retry_interval_seconds: float,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[bool, str]:
    last_message = "No CUDA readiness log line found in training_worker logs."

    for attempt in range(1, max_attempts + 1):
        healthy, message = inspect_cuda_log_text(fetch_log_text())
        if healthy:
            return True, message

        last_message = f"attempt {attempt}/{max_attempts}: {message}"
        if not is_retryable_cuda_failure(message) or attempt == max_attempts:
            return False, last_message

        sleep_fn(retry_interval_seconds)

    return False, last_message


def load_log_text(*, compose_files: tuple[str, ...], service: str, tail: int, log_file: Path | None) -> str:
    if log_file is not None:
        return log_file.read_text(encoding="utf-8")

    command = build_compose_logs_command(compose_files=compose_files, service=service, tail=tail)
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or "docker compose logs command failed")

    return completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compose-file",
        action="append",
        dest="compose_files",
        help="Compose file to include. Defaults to compose.yaml plus docker/compose.gpu.yaml.",
    )
    parser.add_argument("--service", default="training_worker")
    parser.add_argument("--tail", type=int, default=200)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--retry-interval-seconds", type=float, default=3.0)
    args = parser.parse_args()

    compose_files = tuple(args.compose_files or ("compose.yaml", "docker/compose.gpu.yaml"))
    max_attempts = args.max_attempts or (1 if args.log_file is not None else 20)

    def fetch_log_text() -> str:
        return load_log_text(
            compose_files=compose_files,
            service=args.service,
            tail=args.tail,
            log_file=args.log_file,
        )

    healthy, message = wait_for_cuda_validation(
        fetch_log_text,
        max_attempts=max_attempts,
        retry_interval_seconds=args.retry_interval_seconds,
    )
    if not healthy:
        raise SystemExit(f"GPU runtime validation failed for {args.service}: {message}")

    print(f"GPU runtime validation passed for {args.service}: {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
