"""Gymnasium trading environment for RL training."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl_trade_features import BuiltDataset

ACTION_FLAT = 0
ACTION_LONG = 1
ACTION_SHORT = 2


@dataclass(frozen=True, slots=True)
class RewardBreakdown:
    price_pnl: float
    transaction_cost: float
    overtrade_penalty: float
    drawdown_penalty: float
    rr_bonus: float

    @property
    def total(self) -> float:
        return self.price_pnl - self.transaction_cost - self.overtrade_penalty - self.drawdown_penalty + self.rr_bonus


class ForexTradingEnv(gym.Env[np.ndarray, int]):
    """Windowed trading environment over a deterministic built dataset."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        dataset: BuiltDataset,
        *,
        window_size: int = 8,
        initial_equity: float = 10_000.0,
        spread_bps: float = 1.0,
        slippage_bps: float = 0.5,
        overtrade_penalty: float = 0.05,
        drawdown_penalty_factor: float = 2.0,
        rr_target: float = 2.0,
        rr_bonus: float = 0.1,
        atr_feature_name: str | None = None,
        max_episode_steps: int | None = None,
    ) -> None:
        if window_size < 1:
            raise ValueError("RL environment window_size must be at least 1.")
        if dataset.row_count <= window_size:
            raise ValueError("RL environment requires more rows than the requested window size.")
        if "close" not in dataset.feature_columns:
            raise ValueError("RL environment requires a 'close' feature column.")

        self.dataset = dataset
        self.window_size = window_size
        self.initial_equity = initial_equity
        self.spread_bps = spread_bps
        self.slippage_bps = slippage_bps
        self.overtrade_penalty = overtrade_penalty
        self.drawdown_penalty_factor = drawdown_penalty_factor
        self.rr_target = rr_target
        self.rr_bonus = rr_bonus
        self.atr_feature_name = atr_feature_name
        self.max_episode_steps = max_episode_steps or (dataset.row_count - window_size)
        if self.max_episode_steps < 1:
            raise ValueError("RL environment requires at least one step per episode.")
        self.feature_columns = tuple(dataset.feature_columns)
        self.rows = tuple(dataset.rows)

        observation_size = (window_size * len(self.feature_columns)) + 4
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(observation_size,),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(3)

        self.current_index = 0
        self.position = 0
        self.holding_steps = 0
        self.equity = initial_equity
        self.peak_equity = initial_equity
        self.trade_count = 0
        self.step_count = 0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        del options
        self.current_index = self.window_size
        self.position = 0
        self.holding_steps = 0
        self.equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.trade_count = 0
        self.step_count = 0
        return self._build_observation(), self._build_info(RewardBreakdown(0.0, 0.0, 0.0, 0.0, 0.0))

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if not self.action_space.contains(action):
            raise ValueError(f"Action {action} is not valid.")
        if self.current_index >= len(self.rows):
            raise RuntimeError("Environment step called after termination.")

        current_price = self._current_price()
        next_price = self._next_price()
        desired_position = self._action_to_position(action)
        position_changed = desired_position != self.position

        transaction_cost = self._estimate_transaction_cost(current_price) if position_changed else 0.0
        overtrade_penalty = self.overtrade_penalty if position_changed and self.position != 0 and desired_position != 0 else 0.0
        price_pnl = desired_position * (next_price - current_price)

        self.equity += price_pnl - transaction_cost - overtrade_penalty
        drawdown = max(0.0, self.peak_equity - self.equity)
        self.peak_equity = max(self.peak_equity, self.equity)
        drawdown_penalty = (drawdown / self.initial_equity) * self.drawdown_penalty_factor
        risk_unit = max(self._risk_unit(), transaction_cost or (current_price * 0.0001))
        rr_ratio = abs(price_pnl) / risk_unit if risk_unit > 0 else 0.0
        rr_bonus = self.rr_bonus if desired_position != 0 and price_pnl > 0 and rr_ratio >= self.rr_target else 0.0

        breakdown = RewardBreakdown(
            price_pnl=price_pnl,
            transaction_cost=transaction_cost,
            overtrade_penalty=overtrade_penalty,
            drawdown_penalty=drawdown_penalty,
            rr_bonus=rr_bonus,
        )

        self.position = desired_position
        if self.position == 0:
            self.holding_steps = 0
        elif position_changed:
            self.holding_steps = 1
            self.trade_count += 1
        else:
            self.holding_steps += 1

        self.current_index += 1
        self.step_count += 1
        terminated = self.current_index >= len(self.rows)
        truncated = self.step_count >= self.max_episode_steps

        return (
            self._build_observation(),
            float(breakdown.total),
            terminated,
            truncated,
            self._build_info(breakdown, rr_ratio=rr_ratio),
        )

    def _build_observation(self) -> np.ndarray:
        end_index = min(self.current_index, len(self.rows))
        start_index = end_index - self.window_size
        window_rows = self.rows[start_index:end_index]

        feature_values = [
            self._feature_to_float(row.features[column])
            for row in window_rows
            for column in self.feature_columns
        ]
        position_state = [
            float(self.position),
            float(self.holding_steps) / max(1, self.window_size),
            float((self.equity / self.initial_equity) - 1.0),
            float(max(0.0, self.peak_equity - self.equity) / self.initial_equity),
        ]
        return np.asarray(feature_values + position_state, dtype=np.float32)

    def _build_info(self, breakdown: RewardBreakdown, *, rr_ratio: float = 0.0) -> dict[str, Any]:
        return {
            "current_index": self.current_index,
            "position": self.position,
            "equity": self.equity,
            "peak_equity": self.peak_equity,
            "trade_count": self.trade_count,
            "reward_breakdown": {
                "price_pnl": breakdown.price_pnl,
                "transaction_cost": breakdown.transaction_cost,
                "overtrade_penalty": breakdown.overtrade_penalty,
                "drawdown_penalty": breakdown.drawdown_penalty,
                "rr_bonus": breakdown.rr_bonus,
                "total": breakdown.total,
            },
            "risk_to_reward": rr_ratio,
        }

    def _current_price(self) -> float:
        return self._feature_to_float(self.rows[self.current_index - 1].features["close"])

    def _next_price(self) -> float:
        return self._feature_to_float(self.rows[self.current_index].features["close"])

    def _risk_unit(self) -> float:
        if self.atr_feature_name and self.atr_feature_name in self.feature_columns:
            return max(1e-8, self._feature_to_float(self.rows[self.current_index - 1].features[self.atr_feature_name]))
        return max(1e-8, self._current_price() * 0.0005)

    def _estimate_transaction_cost(self, price: float) -> float:
        total_bps = self.spread_bps + self.slippage_bps
        return price * (total_bps / 10_000.0)

    @staticmethod
    def _action_to_position(action: int) -> int:
        if action == ACTION_FLAT:
            return 0
        if action == ACTION_LONG:
            return 1
        return -1

    @staticmethod
    def _feature_to_float(value: Any) -> float:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        return float(value)
