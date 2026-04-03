"""Deterministic candlestick pattern tests."""

from __future__ import annotations

from rl_trade_features import Candle, detect_candlestick_patterns


def candle(open_price: str, high_price: str, low_price: str, close_price: str) -> Candle:
    return Candle(
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
    )


def test_detects_doji() -> None:
    patterns = detect_candlestick_patterns([candle("1.1000", "1.1010", "1.0990", "1.1001")])
    assert patterns.doji is True


def test_detects_hammer_after_bearish_candle() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1050", "1.1060", "1.1000", "1.1010"),
            candle("1.1008", "1.1011", "1.0980", "1.1010"),
        ]
    )
    assert patterns.hammer is True
    assert patterns.hanging_man is False


def test_detects_hanging_man_after_bullish_candle() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1000", "1.1045", "1.0995", "1.1040"),
            candle("1.1040", "1.1043", "1.1005", "1.1042"),
        ]
    )
    assert patterns.hanging_man is True
    assert patterns.hammer is False


def test_detects_bullish_engulfing() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1050", "1.1060", "1.1015", "1.1020"),
            candle("1.1010", "1.1070", "1.1000", "1.1060"),
        ]
    )
    assert patterns.bullish_engulfing is True


def test_detects_bearish_engulfing() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1000", "1.1045", "1.0995", "1.1040"),
            candle("1.1042", "1.1050", "1.0990", "1.0995"),
        ]
    )
    assert patterns.bearish_engulfing is True


def test_detects_morning_star() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1100", "1.1110", "1.0990", "1.1000"),
            candle("1.0995", "1.1005", "1.0985", "1.0998"),
            candle("1.1000", "1.1070", "1.0995", "1.1060"),
        ]
    )
    assert patterns.morning_star is True


def test_detects_evening_star() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1000", "1.1110", "1.0990", "1.1100"),
            candle("1.1098", "1.1105", "1.1092", "1.1095"),
            candle("1.1090", "1.1095", "1.1010", "1.1030"),
        ]
    )
    assert patterns.evening_star is True


def test_detects_shooting_star() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1000", "1.1045", "1.0995", "1.1040"),
            candle("1.1045", "1.1080", "1.1040", "1.1042"),
        ]
    )
    assert patterns.shooting_star is True


def test_detects_pin_bar() -> None:
    patterns = detect_candlestick_patterns([candle("1.2000", "1.2005", "1.1975", "1.2004")])
    assert patterns.pin_bar is True


def test_detects_inside_bar() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1020", "1.1050", "1.1000", "1.1040"),
            candle("1.1030", "1.1040", "1.1010", "1.1025"),
        ]
    )
    assert patterns.inside_bar is True


def test_detects_outside_bar() -> None:
    patterns = detect_candlestick_patterns(
        [
            candle("1.1020", "1.1050", "1.1000", "1.1040"),
            candle("1.1030", "1.1060", "1.0990", "1.1020"),
        ]
    )
    assert patterns.outside_bar is True


def test_pattern_set_as_dict_exposes_all_flags() -> None:
    patterns = detect_candlestick_patterns([candle("1.1000", "1.1010", "1.0990", "1.1001")]).as_dict()
    assert set(patterns) == {
        "doji",
        "hammer",
        "hanging_man",
        "bullish_engulfing",
        "bearish_engulfing",
        "morning_star",
        "evening_star",
        "shooting_star",
        "pin_bar",
        "inside_bar",
        "outside_bar",
    }
