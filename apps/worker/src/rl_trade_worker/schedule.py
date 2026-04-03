"""Periodic scheduler configuration for maintenance tasks."""

from __future__ import annotations

from rl_trade_common import Settings
from rl_trade_worker.queues import MAINTENANCE_QUEUE


def build_beat_schedule(settings: Settings) -> dict[str, dict[str, object]]:
    return {
        "worker-heartbeat": {
            "task": "system.ping",
            "schedule": float(settings.scheduler_heartbeat_interval_seconds),
            "options": {"queue": MAINTENANCE_QUEUE},
        }
    }
