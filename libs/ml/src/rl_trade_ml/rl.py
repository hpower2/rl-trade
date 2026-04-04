"""RL training helpers built around the custom Gymnasium trading environment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Any

from rl_trade_features import BuiltDataset
from rl_trade_ml.rl_env import ForexTradingEnv


@dataclass(frozen=True, slots=True)
class RLTrainingArtifacts:
    algorithm: str
    environment_name: str
    feature_columns: tuple[str, ...]
    label_name: str
    window_size: int
    total_timesteps: int
    device: str
    model: Any
    metrics: dict[str, Any]
    hyperparameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SavedRLArtifacts:
    feature_schema: dict[str, Any]
    model_metadata: dict[str, Any]
    metrics: dict[str, Any]


def train_ppo_policy(
    dataset: BuiltDataset,
    *,
    window_size: int = 8,
    total_timesteps: int = 256,
    n_steps: int = 32,
    batch_size: int = 16,
    learning_rate: float = 3e-4,
    gamma: float = 0.99,
    seed: int = 7,
    atr_feature_name: str | None = None,
    spread_bps: float = 1.0,
    slippage_bps: float = 0.5,
    overtrade_penalty: float = 0.05,
    drawdown_penalty_factor: float = 2.0,
    rr_bonus: float = 0.1,
) -> RLTrainingArtifacts:
    if total_timesteps < 1:
        raise ValueError("RL training total_timesteps must be positive.")

    PPO, Monitor = _require_stable_baselines()
    env = ForexTradingEnv(
        dataset,
        window_size=window_size,
        atr_feature_name=atr_feature_name,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        overtrade_penalty=overtrade_penalty,
        drawdown_penalty_factor=drawdown_penalty_factor,
        rr_bonus=rr_bonus,
    )
    rollout_steps = max(2, min(n_steps, env.max_episode_steps))
    minibatch_size = _resolve_batch_size(requested_batch_size=batch_size, rollout_steps=rollout_steps)
    monitor_env = Monitor(env)
    model = PPO(
        "MlpPolicy",
        monitor_env,
        verbose=0,
        device="cpu",
        seed=seed,
        n_steps=rollout_steps,
        batch_size=minibatch_size,
        learning_rate=learning_rate,
        gamma=gamma,
    )
    model.learn(total_timesteps=total_timesteps, progress_bar=False)

    evaluation = evaluate_trained_policy(
        model,
        dataset=dataset,
        window_size=window_size,
        atr_feature_name=atr_feature_name,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        overtrade_penalty=overtrade_penalty,
        drawdown_penalty_factor=drawdown_penalty_factor,
        rr_bonus=rr_bonus,
    )
    metrics = {
        "algorithm": "ppo",
        "environment_name": "ForexTradingEnv",
        "device": "cpu",
        "total_timesteps": total_timesteps,
        "observation_size": int(env.observation_space.shape[0]),
        "action_count": int(env.action_space.n),
        **evaluation,
    }
    return RLTrainingArtifacts(
        algorithm="ppo",
        environment_name="ForexTradingEnv",
        feature_columns=tuple(dataset.feature_columns),
        label_name=dataset.label_name,
        window_size=window_size,
        total_timesteps=total_timesteps,
        device="cpu",
        model=model,
        metrics=metrics,
        hyperparameters={
            "n_steps": rollout_steps,
            "batch_size": minibatch_size,
            "learning_rate": learning_rate,
            "gamma": gamma,
            "seed": seed,
            "spread_bps": spread_bps,
            "slippage_bps": slippage_bps,
            "overtrade_penalty": overtrade_penalty,
            "drawdown_penalty_factor": drawdown_penalty_factor,
            "rr_bonus": rr_bonus,
            "atr_feature_name": atr_feature_name,
        },
    )


def evaluate_trained_policy(
    model: Any,
    *,
    dataset: BuiltDataset,
    window_size: int,
    atr_feature_name: str | None,
    spread_bps: float,
    slippage_bps: float,
    overtrade_penalty: float,
    drawdown_penalty_factor: float,
    rr_bonus: float,
) -> dict[str, Any]:
    env = ForexTradingEnv(
        dataset,
        window_size=window_size,
        atr_feature_name=atr_feature_name,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        overtrade_penalty=overtrade_penalty,
        drawdown_penalty_factor=drawdown_penalty_factor,
        rr_bonus=rr_bonus,
    )
    observation, _ = env.reset(seed=0)
    terminated = False
    truncated = False
    total_reward = 0.0
    rewards: list[float] = []
    last_info: dict[str, Any] = {}

    while not terminated and not truncated:
        action, _ = model.predict(observation, deterministic=True)
        observation, reward, terminated, truncated, info = env.step(int(action))
        rewards.append(float(reward))
        total_reward += float(reward)
        last_info = info

    if not isfinite(total_reward):
        raise ValueError("RL policy evaluation produced a non-finite total reward.")

    return {
        "episode_steps": len(rewards),
        "mean_step_reward": round(mean(rewards), 6) if rewards else 0.0,
        "total_reward": round(total_reward, 6),
        "final_equity": round(float(last_info.get("equity", env.initial_equity)), 6),
        "trade_count": int(last_info.get("trade_count", 0)),
        "risk_to_reward": round(float(last_info.get("risk_to_reward", 0.0)), 6),
    }


def artifact_payload(training: RLTrainingArtifacts) -> dict[str, Any]:
    return {
        "algorithm": training.algorithm,
        "environment_name": training.environment_name,
        "device": training.device,
        "label_name": training.label_name,
        "feature_columns": list(training.feature_columns),
        "window_size": training.window_size,
        "total_timesteps": training.total_timesteps,
        "hyperparameters": dict(training.hyperparameters),
    }


def save_ppo_artifacts(*, training: RLTrainingArtifacts, artifact_dir: str | Path) -> Path:
    root = Path(artifact_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(
        root / "feature_schema.json",
        {
            "label_name": training.label_name,
            "feature_columns": list(training.feature_columns),
            "window_size": training.window_size,
            "environment_name": training.environment_name,
        },
    )
    write_json_artifact(root / "model.json", artifact_payload(training))
    write_json_artifact(root / "metrics.json", training.metrics)
    checkpoint_path = root / "checkpoint.zip"
    training.model.save(checkpoint_path)
    return checkpoint_path


def load_ppo_artifacts(*, artifact_dir: str | Path) -> SavedRLArtifacts:
    root = Path(artifact_dir)
    return SavedRLArtifacts(
        feature_schema=load_json_artifact(root / "feature_schema.json"),
        model_metadata=load_json_artifact(root / "model.json"),
        metrics=load_json_artifact(root / "metrics.json"),
    )


def load_ppo_checkpoint(path: str | Path) -> Any:
    PPO, _ = _require_stable_baselines()
    return PPO.load(Path(path), device="cpu")


def load_json_artifact(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json_artifact(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _require_stable_baselines() -> tuple[Any, Any]:
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.monitor import Monitor
    except ImportError as exc:  # pragma: no cover - exercised when dependency is missing
        raise RuntimeError("stable-baselines3 is required for RL training helpers.") from exc
    return PPO, Monitor


def _resolve_batch_size(*, requested_batch_size: int, rollout_steps: int) -> int:
    capped_batch_size = max(2, min(requested_batch_size, rollout_steps))
    for candidate in range(capped_batch_size, 1, -1):
        if rollout_steps % candidate == 0:
            return candidate
    return 2
