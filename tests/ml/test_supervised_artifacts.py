"""Supervised artifact reload tests."""

from __future__ import annotations

from pathlib import Path

from rl_trade_ml.supervised import load_supervised_artifacts


def test_load_supervised_artifacts_reads_written_json_bundle(tmp_path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "feature_schema.json").write_text(
        '{"feature_columns":["close"],"label_name":"trade_setup_direction"}',
        encoding="utf-8",
    )
    (artifact_dir / "scaler.json").write_text(
        '{"means":{"close":1.0},"stds":{"close":0.5}}',
        encoding="utf-8",
    )
    (artifact_dir / "model.json").write_text(
        '{"chosen_algorithm":"nearest_centroid","selected_model":{"algorithm":"nearest_centroid"}}',
        encoding="utf-8",
    )
    (artifact_dir / "metrics.json").write_text(
        '{"validation_accuracy":0.75,"device":"cpu"}',
        encoding="utf-8",
    )

    bundle = load_supervised_artifacts(artifact_dir=Path(artifact_dir))

    assert bundle.feature_schema["label_name"] == "trade_setup_direction"
    assert bundle.scaler_state["means"]["close"] == 1.0
    assert bundle.model_state["chosen_algorithm"] == "nearest_centroid"
    assert bundle.metrics["device"] == "cpu"
