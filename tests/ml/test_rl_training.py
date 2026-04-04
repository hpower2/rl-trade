"""Stable-Baselines3 PPO smoke tests for the RL training helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from rl_trade_features import DatasetRow, build_dataset
from rl_trade_ml import load_ppo_artifacts, load_ppo_checkpoint, save_ppo_artifacts, train_ppo_policy


def _build_dataset() -> object:
    base_time = datetime(2026, 1, 3, 9, 0, tzinfo=UTC)
    closes = [
        "1.1000",
        "1.1002",
        "1.1004",
        "1.1007",
        "1.1005",
        "1.1008",
        "1.1010",
        "1.1013",
        "1.1011",
        "1.1015",
        "1.1018",
        "1.1016",
        "1.1019",
        "1.1021",
        "1.1018",
        "1.1022",
    ]
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            DatasetRow(
                timestamp=base_time + timedelta(minutes=index),
                features={
                    "close": Decimal(close),
                    "atr_3": Decimal("0.00005"),
                    "rsi_3": 42 + (index % 10),
                    "pattern_doji": index % 2 == 0,
                    "pattern_inside_bar": index % 3 == 0,
                    "m5_trend": 1 if index % 4 in {1, 2} else -1,
                    "m15_trend": 1 if index % 5 in {2, 3, 4} else 0,
                },
                label="buy" if index % 3 != 0 else "sell",
            )
        )
    return build_dataset(rows=rows, label_name="trade_setup_direction")


def test_train_ppo_policy_smoke_on_sample_dataset() -> None:
    dataset = _build_dataset()

    training = train_ppo_policy(
        dataset,
        window_size=4,
        total_timesteps=64,
        n_steps=16,
        batch_size=8,
        learning_rate=0.001,
        seed=13,
        atr_feature_name="atr_3",
        spread_bps=0.0,
        slippage_bps=0.0,
    )

    assert training.algorithm == "ppo"
    assert training.environment_name == "ForexTradingEnv"
    assert training.device == "cpu"
    assert training.total_timesteps == 64
    assert training.metrics["episode_steps"] > 0
    assert training.metrics["observation_size"] == len(dataset.feature_columns) * 4 + 4
    assert training.metrics["action_count"] == 3
    assert isinstance(training.metrics["total_reward"], float)
    assert training.model is not None


def test_save_and_load_ppo_artifacts_round_trip(tmp_path) -> None:
    dataset = _build_dataset()
    training = train_ppo_policy(
        dataset,
        window_size=4,
        total_timesteps=64,
        n_steps=16,
        batch_size=8,
        learning_rate=0.001,
        seed=21,
        atr_feature_name="atr_3",
        spread_bps=0.0,
        slippage_bps=0.0,
    )

    checkpoint_path = save_ppo_artifacts(training=training, artifact_dir=tmp_path / "rl-artifacts")
    loaded_bundle = load_ppo_artifacts(artifact_dir=tmp_path / "rl-artifacts")
    loaded_model = load_ppo_checkpoint(checkpoint_path)

    assert checkpoint_path.exists()
    assert loaded_bundle.feature_schema["label_name"] == "trade_setup_direction"
    assert loaded_bundle.model_metadata["algorithm"] == "ppo"
    assert loaded_bundle.metrics["device"] == "cpu"

    observation = training.model.get_env().reset()
    action, _ = loaded_model.predict(observation, deterministic=True)
    assert int(action[0]) in {0, 1, 2}
