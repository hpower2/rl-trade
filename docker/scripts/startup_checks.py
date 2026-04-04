"""Container startup checks for Docker Compose services."""

from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import time
from collections.abc import Callable

from redis import Redis
from sqlalchemy import create_engine, text

from rl_trade_common import get_settings

CheckFn = Callable[[], tuple[bool, str]]

REQUIRED_CHECKS: dict[str, tuple[str, ...]] = {
    "api": ("database", "redis"),
    "worker": ("database", "redis"),
    "training_worker": ("database", "redis"),
    "scheduler": ("database", "redis"),
    "migrate": ("database",),
}

OPTIONAL_CHECKS: dict[str, tuple[str, ...]] = {
    "api": ("mt5",),
    "worker": ("mt5",),
    "training_worker": ("mt5", "cuda"),
    "scheduler": ("mt5",),
    "migrate": (),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True)
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("STARTUP_MAX_ATTEMPTS", "20")))
    parser.add_argument(
        "--retry-interval-seconds",
        type=float,
        default=float(os.getenv("STARTUP_RETRY_INTERVAL_SECONDS", "3")),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [startup-checks] %(message)s",
    )
    logger = logging.getLogger("docker.startup_checks")
    settings = get_settings()

    logger.info("Running startup checks.", extra={"service": args.service})

    for check_name in REQUIRED_CHECKS.get(args.service, ()):
        run_required_check(
            check_name=check_name,
            check_fn=build_check_map(settings)[check_name],
            logger=logger,
            max_attempts=args.max_attempts,
            retry_interval_seconds=args.retry_interval_seconds,
        )

    for check_name in OPTIONAL_CHECKS.get(args.service, ()):
        healthy, message = build_check_map(settings)[check_name]()
        log_optional_result(check_name=check_name, healthy=healthy, logger=logger, message=message)

    logger.info("Startup checks completed.", extra={"service": args.service})
    return 0


def build_check_map(settings) -> dict[str, CheckFn]:
    require_cuda = os.getenv("REQUIRE_CUDA", "false").strip().lower() == "true"

    return {
        "database": lambda: check_database(settings.database_url),
        "redis": lambda: check_redis(settings.redis_url),
        "mt5": lambda: check_mt5(settings.mt5_terminal_path, settings.mt5_login, settings.mt5_server),
        "cuda": lambda: check_cuda(require_cuda=require_cuda),
    }


def run_required_check(
    *,
    check_name: str,
    check_fn: CheckFn,
    logger: logging.Logger,
    max_attempts: int,
    retry_interval_seconds: float,
) -> None:
    for attempt in range(1, max_attempts + 1):
        healthy, message = check_fn()
        if healthy:
            logger.info("%s check passed: %s", check_name, message)
            return

        logger.warning(
            "%s check failed on attempt %s/%s: %s",
            check_name,
            attempt,
            max_attempts,
            message,
        )
        if attempt == max_attempts:
            raise SystemExit(f"{check_name} startup check failed after {max_attempts} attempts: {message}")
        time.sleep(retry_interval_seconds)


def log_optional_result(
    *,
    check_name: str,
    healthy: bool,
    logger: logging.Logger,
    message: str,
) -> None:
    if healthy:
        logger.info("%s check: %s", check_name, message)
    else:
        logger.warning("%s check degraded: %s", check_name, message)


def check_database(database_url: str) -> tuple[bool, str]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - integration behavior
        return False, f"database unavailable: {exc}"
    finally:
        engine.dispose()

    return True, "connected to database and executed SELECT 1"


def check_redis(redis_url: str) -> tuple[bool, str]:
    client = Redis.from_url(redis_url)
    try:
        client.ping()
    except Exception as exc:  # pragma: no cover - integration behavior
        return False, f"redis unavailable: {exc}"

    return True, "ping succeeded"


def check_mt5(mt5_terminal_path: str, mt5_login: str | None, mt5_server: str | None) -> tuple[bool, str]:
    package_installed = importlib.util.find_spec("MetaTrader5") is not None
    terminal_exists = bool(mt5_terminal_path and os.path.exists(mt5_terminal_path))
    credentials_present = bool((mt5_login or "").strip() and (mt5_server or "").strip())

    if not credentials_present:
        return False, "credentials are not configured; MT5 features will remain unavailable"
    if not package_installed:
        return False, "MetaTrader5 package is not installed in this image"
    if not terminal_exists:
        return False, f"terminal path does not exist: {mt5_terminal_path}"

    return True, "terminal path and credentials are configured"


def check_cuda(*, require_cuda: bool) -> tuple[bool, str]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - integration behavior
        if require_cuda:
            return False, f"torch import failed while CUDA is required: {exc}"
        return False, f"torch import failed; worker will stay CPU-only: {exc}"

    if not torch.cuda.is_available():
        if require_cuda:
            return False, "CUDA is required but no device is available"
        return False, "CUDA is unavailable; training will degrade to CPU mode"

    return True, f"CUDA available with {torch.cuda.device_count()} device(s)"


if __name__ == "__main__":
    raise SystemExit(main())
