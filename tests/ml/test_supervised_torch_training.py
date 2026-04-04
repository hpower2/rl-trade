"""PyTorch supervised training smoke tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from rl_trade_features import DatasetRow, build_dataset
from rl_trade_ml import train_torch_mlp


def test_train_torch_mlp_smoke_on_sample_dataset() -> None:
    base_time = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    rows = []
    labels = ["buy", "buy", "buy", "sell", "sell", "no_trade", "buy", "sell", "no_trade"]
    for index, label in enumerate(labels):
        rows.append(
            DatasetRow(
                timestamp=base_time + timedelta(minutes=index),
                features={
                    "close": Decimal("1.1000") + Decimal(index) * Decimal("0.0002"),
                    "rsi_3": 45 + index,
                    "pattern_doji": index % 2 == 0,
                },
                label=label,
            )
        )

    dataset = build_dataset(rows=rows, label_name="trade_setup_direction")
    training = train_torch_mlp(
        dataset,
        validation_ratio=0.25,
        walk_forward_folds=2,
        hidden_dim=8,
        epochs=10,
        learning_rate=0.02,
        seed=11,
    )

    assert training.chosen_algorithm == "torch_mlp"
    assert training.device in {"cpu", "cuda"}
    assert training.metrics["validation_accuracy"] >= 0.0
    assert training.metrics["walk_forward_accuracy"] >= 0.0
    assert training.checkpoint_state is not None
    assert training.checkpoint_state["input_dim"] == len(dataset.feature_columns)
    assert training.checkpoint_state["state_dict"]
