"""Approval gating unit tests."""

from __future__ import annotations

from rl_trade_common.settings import Settings
from rl_trade_trading import evaluate_model_approval


def test_evaluate_model_approval_allows_metrics_that_clear_all_thresholds() -> None:
    decision = evaluate_model_approval(
        settings=Settings(_env_file=None),
        confidence=74.0,
        risk_to_reward=2.5,
        sample_size=140,
        max_drawdown=12.0,
        has_critical_data_issue=False,
    )

    assert decision.approved is True
    assert decision.reasons == ()


def test_evaluate_model_approval_collects_rejection_reasons() -> None:
    decision = evaluate_model_approval(
        settings=Settings(_env_file=None),
        confidence=61.0,
        risk_to_reward=1.7,
        sample_size=40,
        max_drawdown=28.0,
        has_critical_data_issue=True,
    )

    assert decision.approved is False
    assert decision.reasons == (
        "confidence_below_threshold",
        "risk_to_reward_below_threshold",
        "insufficient_sample_size",
        "drawdown_above_threshold",
        "critical_data_issue",
    )
