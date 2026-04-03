"""Feature calculation unit tests."""

from __future__ import annotations

from decimal import Decimal

from rl_trade_features import Candle, compute_atr, compute_candle_structure, compute_ema, compute_rsi, compute_sma, compute_true_range


def test_compute_sma_returns_windowed_average() -> None:
    result = compute_sma(["1", "2", "3", "4"], window=3)
    assert result == [None, None, Decimal("2"), Decimal("3")]


def test_compute_ema_uses_sma_seed() -> None:
    result = compute_ema(["1", "2", "3", "4"], window=3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == Decimal("2")
    assert result[3] == Decimal("3")


def test_compute_rsi_reaches_extremes_for_one_sided_moves() -> None:
    bullish = compute_rsi(["1", "2", "3", "4"], window=2)
    bearish = compute_rsi(["4", "3", "2", "1"], window=2)

    assert bullish[-1] == Decimal("100")
    assert bearish[-1] == Decimal("0")


def test_compute_true_range_captures_gap() -> None:
    candles = [
        Candle(open="10", high="12", low="9", close="11"),
        Candle(open="13", high="14", low="12", close="13"),
    ]

    result = compute_true_range(candles)

    assert result == [Decimal("3"), Decimal("3")]


def test_compute_atr_uses_wilder_smoothing() -> None:
    candles = [
        Candle(open="10", high="12", low="9", close="11"),
        Candle(open="11", high="13", low="10", close="12"),
        Candle(open="12", high="14", low="11", close="13"),
    ]

    result = compute_atr(candles, window=2)

    assert result[0] is None
    assert result[1] == Decimal("3")
    assert result[2] == Decimal("3")


def test_compute_candle_structure_exposes_ratios_and_direction() -> None:
    structure = compute_candle_structure(Candle(open="10", high="14", low="8", close="13"))

    assert structure.direction == 1
    assert structure.range_size == Decimal("6")
    assert structure.body_size == Decimal("3")
    assert structure.upper_shadow == Decimal("1")
    assert structure.lower_shadow == Decimal("2")
    assert structure.body_ratio == Decimal("0.5")
    assert structure.upper_shadow_ratio == Decimal("0.1666666666666666666666666667")
    assert structure.lower_shadow_ratio == Decimal("0.3333333333333333333333333333")
    assert structure.close_position_in_range == Decimal("0.8333333333333333333333333333")


def test_compute_candle_structure_handles_flat_candle_range() -> None:
    structure = compute_candle_structure(Candle(open="10", high="10", low="10", close="10"))

    assert structure.direction == 0
    assert structure.body_ratio == Decimal("0")
    assert structure.close_position_in_range == Decimal("0.5")
