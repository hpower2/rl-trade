"""Deterministic candlestick pattern detection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

ZERO = Decimal("0")
DOJI_BODY_RATIO = Decimal("0.10")
SMALL_BODY_RATIO = Decimal("0.35")
LONG_BODY_RATIO = Decimal("0.50")
SHADOW_MULTIPLIER = Decimal("2.0")


@dataclass(frozen=True, slots=True)
class Candle:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "open", _to_decimal(self.open))
        object.__setattr__(self, "high", _to_decimal(self.high))
        object.__setattr__(self, "low", _to_decimal(self.low))
        object.__setattr__(self, "close", _to_decimal(self.close))
        if self.high < max(self.open, self.close):
            raise ValueError("high must be at least max(open, close).")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be at most min(open, close).")
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low.")

    @property
    def range_size(self) -> Decimal:
        return self.high - self.low

    @property
    def body_size(self) -> Decimal:
        return abs(self.close - self.open)

    @property
    def upper_shadow(self) -> Decimal:
        return self.high - max(self.open, self.close)

    @property
    def lower_shadow(self) -> Decimal:
        return min(self.open, self.close) - self.low

    @property
    def midpoint(self) -> Decimal:
        return (self.open + self.close) / Decimal("2")

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass(frozen=True, slots=True)
class CandlestickPatternSet:
    doji: bool = False
    hammer: bool = False
    hanging_man: bool = False
    bullish_engulfing: bool = False
    bearish_engulfing: bool = False
    morning_star: bool = False
    evening_star: bool = False
    shooting_star: bool = False
    pin_bar: bool = False
    inside_bar: bool = False
    outside_bar: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "doji": self.doji,
            "hammer": self.hammer,
            "hanging_man": self.hanging_man,
            "bullish_engulfing": self.bullish_engulfing,
            "bearish_engulfing": self.bearish_engulfing,
            "morning_star": self.morning_star,
            "evening_star": self.evening_star,
            "shooting_star": self.shooting_star,
            "pin_bar": self.pin_bar,
            "inside_bar": self.inside_bar,
            "outside_bar": self.outside_bar,
        }


def detect_candlestick_patterns(candles: Sequence[Candle]) -> CandlestickPatternSet:
    if not candles:
        raise ValueError("candles must contain at least one candle.")

    current = candles[-1]
    previous = candles[-2] if len(candles) >= 2 else None
    first = candles[-3] if len(candles) >= 3 else None

    doji = _is_doji(current)
    hammer_shape = _is_hammer_shape(current)
    inverted_shape = _is_inverted_hammer_shape(current)

    return CandlestickPatternSet(
        doji=doji,
        hammer=hammer_shape and previous is not None and previous.is_bearish,
        hanging_man=hammer_shape and previous is not None and previous.is_bullish,
        bullish_engulfing=_is_bullish_engulfing(previous, current),
        bearish_engulfing=_is_bearish_engulfing(previous, current),
        morning_star=_is_morning_star(first, previous, current),
        evening_star=_is_evening_star(first, previous, current),
        shooting_star=inverted_shape and previous is not None and previous.is_bullish,
        pin_bar=_is_pin_bar(current),
        inside_bar=_is_inside_bar(previous, current),
        outside_bar=_is_outside_bar(previous, current),
    )


def _is_doji(candle: Candle) -> bool:
    return _ratio(candle.body_size, candle.range_size) <= DOJI_BODY_RATIO


def _is_small_body(candle: Candle) -> bool:
    return _ratio(candle.body_size, candle.range_size) <= SMALL_BODY_RATIO


def _is_long_body(candle: Candle) -> bool:
    return _ratio(candle.body_size, candle.range_size) >= LONG_BODY_RATIO


def _is_hammer_shape(candle: Candle) -> bool:
    body = max(candle.body_size, Decimal("0.0000001"))
    return (
        candle.lower_shadow >= body * SHADOW_MULTIPLIER
        and candle.upper_shadow <= body
        and _ratio(candle.body_size, candle.range_size) <= SMALL_BODY_RATIO
    )


def _is_inverted_hammer_shape(candle: Candle) -> bool:
    body = max(candle.body_size, Decimal("0.0000001"))
    return (
        candle.upper_shadow >= body * SHADOW_MULTIPLIER
        and candle.lower_shadow <= body
        and _ratio(candle.body_size, candle.range_size) <= SMALL_BODY_RATIO
    )


def _is_pin_bar(candle: Candle) -> bool:
    body = max(candle.body_size, Decimal("0.0000001"))
    dominant_shadow = max(candle.upper_shadow, candle.lower_shadow)
    minor_shadow = min(candle.upper_shadow, candle.lower_shadow)
    return dominant_shadow >= body * SHADOW_MULTIPLIER and minor_shadow <= body and _is_small_body(candle)


def _is_inside_bar(previous: Candle | None, current: Candle) -> bool:
    return previous is not None and current.high < previous.high and current.low > previous.low


def _is_outside_bar(previous: Candle | None, current: Candle) -> bool:
    return previous is not None and current.high > previous.high and current.low < previous.low


def _is_bullish_engulfing(previous: Candle | None, current: Candle) -> bool:
    return (
        previous is not None
        and previous.is_bearish
        and current.is_bullish
        and current.open <= previous.close
        and current.close >= previous.open
    )


def _is_bearish_engulfing(previous: Candle | None, current: Candle) -> bool:
    return (
        previous is not None
        and previous.is_bullish
        and current.is_bearish
        and current.open >= previous.close
        and current.close <= previous.open
    )


def _is_morning_star(first: Candle | None, second: Candle | None, current: Candle) -> bool:
    return (
        first is not None
        and second is not None
        and first.is_bearish
        and _is_long_body(first)
        and _is_small_body(second)
        and current.is_bullish
        and current.close >= first.midpoint
    )


def _is_evening_star(first: Candle | None, second: Candle | None, current: Candle) -> bool:
    return (
        first is not None
        and second is not None
        and first.is_bullish
        and _is_long_body(first)
        and _is_small_body(second)
        and current.is_bearish
        and current.close <= first.midpoint
    )


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= ZERO:
        return ZERO
    return numerator / denominator


def _to_decimal(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
