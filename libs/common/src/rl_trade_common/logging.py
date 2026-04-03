"""Centralized logging configuration."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from rl_trade_common.settings import Settings, get_settings


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": getattr(record, "service", "unknown"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class ServiceNameFilter(logging.Filter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service_name
        return True


def configure_logging(service_name: str, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    level = getattr(logging, active_settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler()
    handler.addFilter(ServiceNameFilter(service_name))

    if active_settings.log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(service)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
