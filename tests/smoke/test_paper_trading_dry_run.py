"""Smoke coverage for the manual paper-trading dry-run path."""

from __future__ import annotations

from io import StringIO

from rl_trade_api.tools.paper_trading_dry_run import run_dry_run


def test_manual_paper_trading_dry_run_path_completes() -> None:
    output = StringIO()

    summary = run_dry_run(stdout=output)

    assert summary.started is True
    assert summary.signal_status == "accepted"
    assert summary.opening_order_status == "submitted"
    assert summary.first_sync_orders_updated == 1
    assert summary.first_sync_positions_updated == 2
    assert summary.open_position_count_after_sync == 1
    assert summary.closing_order_status == "submitted"
    assert summary.second_sync_positions_updated == 1
    assert summary.final_position_status == "closed"
    assert summary.stopped is True
    assert "start enabled=True" in output.getvalue()
    assert "final_position status=closed" in output.getvalue()
