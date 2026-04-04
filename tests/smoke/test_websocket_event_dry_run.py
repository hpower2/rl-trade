"""Smoke coverage for the manual WebSocket live-update dry run."""

from __future__ import annotations

from io import StringIO

from rl_trade_api.tools.websocket_event_dry_run import run_dry_run


def test_manual_websocket_event_dry_run_path_completes() -> None:
    output = StringIO()

    summary = run_dry_run(stdout=output)

    assert summary.ingestion_event_count >= 3
    assert summary.ingestion_statuses[0] == "running"
    assert summary.ingestion_final_status == "succeeded"
    assert summary.training_event_count >= 4
    assert summary.training_statuses[0] == "running"
    assert summary.training_final_status == "succeeded"
    assert "ingestion statuses=" in output.getvalue()
    assert "training statuses=" in output.getvalue()
