"""Leakage-safe label generation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Sequence

from rl_trade_features.patterns import Candle

ZERO = Decimal("0")


class DirectionLabel(str, Enum):
    BUY = "buy"
    SELL = "sell"
    NO_TRADE = "no_trade"


@dataclass(frozen=True, slots=True)
class ForwardReturnLabel:
    horizon_bars: int
    future_close: Decimal
    return_ratio: Decimal


@dataclass(frozen=True, slots=True)
class TradeSetupLabel:
    horizon_bars: int
    direction: DirectionLabel
    upside_ratio: Decimal
    downside_ratio: Decimal
    future_close_return_ratio: Decimal


def generate_forward_return_labels(
    candles: Sequence[Candle],
    *,
    horizon_bars: int,
) -> list[ForwardReturnLabel | None]:
    _validate_horizon(horizon_bars)
    labels: list[ForwardReturnLabel | None] = []

    for index, candle in enumerate(candles):
        target_index = index + horizon_bars
        if target_index >= len(candles):
            labels.append(None)
            continue

        future_close = candles[target_index].close
        labels.append(
            ForwardReturnLabel(
                horizon_bars=horizon_bars,
                future_close=future_close,
                return_ratio=_return_ratio(entry=candle.close, exit_price=future_close),
            )
        )

    return labels


def generate_trade_setup_labels(
    candles: Sequence[Candle],
    *,
    horizon_bars: int,
    min_move_ratio: Decimal | float | int | str = Decimal("0.001"),
) -> list[TradeSetupLabel | None]:
    _validate_horizon(horizon_bars)
    minimum_move = _to_decimal(min_move_ratio)
    labels: list[TradeSetupLabel | None] = []

    for index, candle in enumerate(candles):
        future_window = candles[index + 1 : index + 1 + horizon_bars]
        if len(future_window) < horizon_bars:
            labels.append(None)
            continue

        highest_price = max(future.high for future in future_window)
        lowest_price = min(future.low for future in future_window)
        final_close = future_window[-1].close

        upside_ratio = _return_ratio(entry=candle.close, exit_price=highest_price)
        downside_ratio = _return_ratio(entry=lowest_price, exit_price=candle.close)
        future_close_return = _return_ratio(entry=candle.close, exit_price=final_close)

        direction = DirectionLabel.NO_TRADE
        if upside_ratio >= minimum_move and upside_ratio > downside_ratio:
            direction = DirectionLabel.BUY
        elif downside_ratio >= minimum_move and downside_ratio > upside_ratio:
            direction = DirectionLabel.SELL

        labels.append(
            TradeSetupLabel(
                horizon_bars=horizon_bars,
                direction=direction,
                upside_ratio=upside_ratio,
                downside_ratio=downside_ratio,
                future_close_return_ratio=future_close_return,
            )
        )

    return labels


def _return_ratio(*, entry: Decimal, exit_price: Decimal) -> Decimal:
    if entry == ZERO:
        return ZERO
    return (exit_price - entry) / entry


def _validate_horizon(horizon_bars: int) -> None:
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be greater than or equal to 1.")


def _to_decimal(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
