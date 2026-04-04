"""Verify that the local Docker host is plausibly ready for GPU Compose runs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_docker_info_payload(payload: str) -> dict[str, Any]:
    normalized = payload.strip()
    if not normalized:
        raise ValueError("docker info payload is empty")

    decoded = json.loads(normalized)
    if not isinstance(decoded, dict):
        raise ValueError("docker info payload must decode to an object")
    return decoded


def _normalize_runtimes(raw_runtimes: Any) -> set[str]:
    if isinstance(raw_runtimes, dict):
        return {str(name).strip().lower() for name in raw_runtimes if str(name).strip()}
    if isinstance(raw_runtimes, list):
        names: set[str] = set()
        for item in raw_runtimes:
            if isinstance(item, str) and item.strip():
                names.add(item.strip().lower())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("Name")
                if isinstance(name, str) and name.strip():
                    names.add(name.strip().lower())
        return names
    return set()


def inspect_gpu_host_info(info: dict[str, Any]) -> tuple[bool, list[str]]:
    runtimes = _normalize_runtimes(info.get("Runtimes"))
    default_runtime = str(info.get("DefaultRuntime") or "").strip().lower()
    driver_status = info.get("DriverStatus")
    details: list[str] = []

    if "nvidia" not in runtimes:
        return False, [
            "Docker host does not advertise an 'nvidia' runtime. Install/configure the NVIDIA container runtime first."
        ]

    details.append(f"nvidia runtime detected (available_runtimes={','.join(sorted(runtimes))})")
    if default_runtime:
        details.append(f"default_runtime={default_runtime}")

    if isinstance(driver_status, list):
        flattened = " ".join(
            " ".join(str(part) for part in row if part is not None)
            for row in driver_status
            if isinstance(row, list)
        ).lower()
        if "nvidia" in flattened:
            details.append("docker driver status references NVIDIA support")

    return True, details


def load_docker_info(*, info_file: Path | None) -> dict[str, Any]:
    if info_file is not None:
        return parse_docker_info_payload(info_file.read_text(encoding="utf-8"))

    completed = subprocess.run(
        ["docker", "info", "--format", "{{json .}}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or "docker info command failed")

    return parse_docker_info_payload(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--info-file", type=Path)
    args = parser.parse_args()

    info = load_docker_info(info_file=args.info_file)
    healthy, details = inspect_gpu_host_info(info)
    if not healthy:
        raise SystemExit("GPU host preflight failed:\n- " + "\n- ".join(details))

    print("GPU host preflight passed: " + ", ".join(details))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
