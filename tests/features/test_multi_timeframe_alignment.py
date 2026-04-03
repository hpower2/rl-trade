"""Multi-timeframe alignment tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rl_trade_features import TimeframeFeaturePoint, align_timeframe_features


def test_align_timeframe_features_uses_latest_available_past_point() -> None:
    rows = align_timeframe_features(
        base_timestamps=[
            datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 9, 5, tzinfo=UTC),
            datetime(2026, 1, 1, 9, 10, tzinfo=UTC),
        ],
        source_points=[
            TimeframeFeaturePoint(
                timestamp=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                values={"trend": 1, "bias": "long"},
            ),
            TimeframeFeaturePoint(
                timestamp=datetime(2026, 1, 1, 9, 10, tzinfo=UTC),
                values={"trend": -1, "bias": "short"},
            ),
        ],
        prefix="m15",
    )

    assert rows[0]["m15_trend"] == 1
    assert rows[1]["m15_trend"] == 1
    assert rows[1]["m15_age_seconds"] == 300
    assert rows[2]["m15_trend"] == -1
    assert rows[2]["m15_bias"] == "short"


def test_align_timeframe_features_does_not_leak_future_source_points() -> None:
    rows = align_timeframe_features(
        base_timestamps=[datetime(2026, 1, 1, 9, 4, tzinfo=UTC)],
        source_points=[
            TimeframeFeaturePoint(
                timestamp=datetime(2026, 1, 1, 9, 5, tzinfo=UTC),
                values={"trend": 1},
            )
        ],
        prefix="m5",
    )

    assert rows == [
        {
            "m5_timestamp": None,
            "m5_age_seconds": None,
            "m5_trend": None,
        }
    ]


def test_align_timeframe_features_can_drop_stale_values() -> None:
    rows = align_timeframe_features(
        base_timestamps=[datetime(2026, 1, 1, 9, 15, tzinfo=UTC)],
        source_points=[
            TimeframeFeaturePoint(
                timestamp=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
                values={"trend": 1},
            )
        ],
        prefix="m15",
        max_age=timedelta(minutes=10),
    )

    assert rows[0]["m15_trend"] is None
    assert rows[0]["m15_timestamp"] is None


def test_align_timeframe_features_normalizes_naive_timestamps_to_utc() -> None:
    rows = align_timeframe_features(
        base_timestamps=[datetime(2026, 1, 1, 9, 5)],
        source_points=[
            TimeframeFeaturePoint(
                timestamp=datetime(2026, 1, 1, 9, 0),
                values={"trend": 1},
            )
        ],
        prefix="m5",
    )

    assert rows[0]["m5_timestamp"] == "2026-01-01T09:00:00+00:00"
    assert rows[0]["m5_age_seconds"] == 300
    assert rows[0]["m5_trend"] == 1
