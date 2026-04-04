"""RL trading environment tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from rl_trade_features import DatasetRow, build_dataset
from rl_trade_ml import ACTION_LONG, ACTION_SHORT, ForexTradingEnv


def _build_dataset(*, closes: list[str]) -> object:
    base_time = datetime(2026, 1, 2, 9, 0, tzinfo=UTC)
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            DatasetRow(
                timestamp=base_time + timedelta(minutes=index),
                features={
                    "close": Decimal(close),
                    "atr_3": Decimal("0.00005"),
                    "rsi_3": 40 + index,
                    "pattern_doji": index % 2 == 0,
                    "m5_trend": (index % 3) - 1,
                },
                label="buy" if index % 2 == 0 else "sell",
            )
        )
    return build_dataset(rows=rows, label_name="trade_setup_direction")


def test_reset_returns_windowed_observation_and_zeroed_state() -> None:
    dataset = _build_dataset(closes=["1.1000", "1.1002", "1.1004", "1.1006", "1.1008", "1.1010"])
    env = ForexTradingEnv(dataset, window_size=3, atr_feature_name="atr_3")

    observation, info = env.reset()

    assert observation.shape == (len(dataset.feature_columns) * 3 + 4,)
    assert info["current_index"] == 3
    assert info["position"] == 0
    assert info["trade_count"] == 0
    assert info["reward_breakdown"]["total"] == 0.0


def test_long_step_applies_profit_and_rr_bonus() -> None:
    dataset = _build_dataset(closes=["1.1000", "1.1002", "1.1004", "1.1008", "1.1010", "1.1012"])
    env = ForexTradingEnv(
        dataset,
        window_size=3,
        atr_feature_name="atr_3",
        spread_bps=0.0,
        slippage_bps=0.0,
        rr_bonus=0.2,
    )
    env.reset()

    _, reward, terminated, truncated, info = env.step(ACTION_LONG)

    assert reward > 0.0
    assert not terminated
    assert not truncated
    assert info["position"] == 1
    assert info["trade_count"] == 1
    assert info["risk_to_reward"] >= 2.0
    assert info["reward_breakdown"]["price_pnl"] > 0.0
    assert info["reward_breakdown"]["rr_bonus"] == pytest.approx(0.2)


def test_reversal_applies_overtrade_penalty() -> None:
    dataset = _build_dataset(closes=["1.1000", "1.1002", "1.1004", "1.1008", "1.1003", "1.1001", "1.0998"])
    env = ForexTradingEnv(
        dataset,
        window_size=3,
        atr_feature_name="atr_3",
        spread_bps=0.0,
        slippage_bps=0.0,
        overtrade_penalty=0.15,
    )
    env.reset()
    env.step(ACTION_LONG)

    _, reward, _, _, info = env.step(ACTION_SHORT)

    assert reward < info["reward_breakdown"]["price_pnl"]
    assert info["position"] == -1
    assert info["trade_count"] == 2
    assert info["reward_breakdown"]["overtrade_penalty"] == pytest.approx(0.15)


def test_losing_step_applies_drawdown_penalty() -> None:
    dataset = _build_dataset(closes=["1.1000", "1.1002", "1.1004", "1.1001", "1.0999", "1.0997"])
    env = ForexTradingEnv(
        dataset,
        window_size=3,
        atr_feature_name="atr_3",
        spread_bps=0.0,
        slippage_bps=0.0,
        drawdown_penalty_factor=3.0,
    )
    env.reset()

    _, reward, _, _, info = env.step(ACTION_LONG)

    assert reward < 0.0
    assert info["reward_breakdown"]["price_pnl"] < 0.0
    assert info["reward_breakdown"]["drawdown_penalty"] > 0.0


def test_environment_requires_close_feature_column() -> None:
    dataset = build_dataset(
        rows=(
            DatasetRow(
                timestamp=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
                features={"atr_3": Decimal("0.00005")},
                label="buy",
            ),
            DatasetRow(
                timestamp=datetime(2026, 1, 2, 9, 1, tzinfo=UTC),
                features={"atr_3": Decimal("0.00005")},
                label="sell",
            ),
            DatasetRow(
                timestamp=datetime(2026, 1, 2, 9, 2, tzinfo=UTC),
                features={"atr_3": Decimal("0.00005")},
                label="buy",
            ),
        ),
        label_name="trade_setup_direction",
    )

    with pytest.raises(ValueError, match="requires a 'close' feature column"):
        ForexTradingEnv(dataset, window_size=1)
