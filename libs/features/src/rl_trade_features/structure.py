"""Single-candle structural feature helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rl_trade_features.patterns import Candle

ZERO = Decimal("0")
HALF = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class CandleStructure:
    direction: int
    range_size: Decimal
    body_size: Decimal
    upper_shadow: Decimal
    lower_shadow: Decimal
    body_ratio: Decimal
    upper_shadow_ratio: Decimal
    lower_shadow_ratio: Decimal
    close_position_in_range: Decimal

    def as_dict(self) -> dict[str, Decimal | int]:
        return {
            "direction": self.direction,
            "range_size": self.range_size,
            "body_size": self.body_size,
            "upper_shadow": self.upper_shadow,
            "lower_shadow": self.lower_shadow,
            "body_ratio": self.body_ratio,
            "upper_shadow_ratio": self.upper_shadow_ratio,
            "lower_shadow_ratio": self.lower_shadow_ratio,
            "close_position_in_range": self.close_position_in_range,
        }


def compute_candle_structure(candle: Candle) -> CandleStructure:
    range_size = candle.range_size
    if range_size <= ZERO:
        return CandleStructure(
            direction=0,
            range_size=range_size,
            body_size=candle.body_size,
            upper_shadow=candle.upper_shadow,
            lower_shadow=candle.lower_shadow,
            body_ratio=ZERO,
            upper_shadow_ratio=ZERO,
            lower_shadow_ratio=ZERO,
            close_position_in_range=HALF,
        )

    direction = 1 if candle.is_bullish else -1 if candle.is_bearish else 0
    return CandleStructure(
        direction=direction,
        range_size=range_size,
        body_size=candle.body_size,
        upper_shadow=candle.upper_shadow,
        lower_shadow=candle.lower_shadow,
        body_ratio=candle.body_size / range_size,
        upper_shadow_ratio=candle.upper_shadow / range_size,
        lower_shadow_ratio=candle.lower_shadow / range_size,
        close_position_in_range=(candle.close - candle.low) / range_size,
    )
