"""Deterministic technical indicator helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from rl_trade_features.patterns import Candle

ZERO = Decimal("0")


def compute_sma(values: Sequence[Decimal | float | int | str], window: int) -> list[Decimal | None]:
    _validate_window(window)
    decimals = [_to_decimal(value) for value in values]
    result: list[Decimal | None] = []
    rolling_sum = ZERO

    for index, value in enumerate(decimals):
        rolling_sum += value
        if index >= window:
            rolling_sum -= decimals[index - window]

        if index + 1 < window:
            result.append(None)
            continue

        result.append(rolling_sum / Decimal(window))

    return result


def compute_ema(values: Sequence[Decimal | float | int | str], window: int) -> list[Decimal | None]:
    _validate_window(window)
    decimals = [_to_decimal(value) for value in values]
    result: list[Decimal | None] = [None] * len(decimals)
    if len(decimals) < window:
        return result

    multiplier = Decimal("2") / Decimal(window + 1)
    seed = sum(decimals[:window], start=ZERO) / Decimal(window)
    result[window - 1] = seed
    ema = seed

    for index in range(window, len(decimals)):
        ema = ((decimals[index] - ema) * multiplier) + ema
        result[index] = ema

    return result


def compute_rsi(values: Sequence[Decimal | float | int | str], window: int = 14) -> list[Decimal | None]:
    _validate_window(window)
    closes = [_to_decimal(value) for value in values]
    result: list[Decimal | None] = [None] * len(closes)
    if len(closes) <= window:
        return result

    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for index in range(1, len(closes)):
        delta = closes[index] - closes[index - 1]
        gains.append(max(delta, ZERO))
        losses.append(max(-delta, ZERO))

    average_gain = sum(gains[:window], start=ZERO) / Decimal(window)
    average_loss = sum(losses[:window], start=ZERO) / Decimal(window)
    result[window] = _rsi_from_averages(average_gain, average_loss)

    for index in range(window, len(gains)):
        average_gain = ((average_gain * Decimal(window - 1)) + gains[index]) / Decimal(window)
        average_loss = ((average_loss * Decimal(window - 1)) + losses[index]) / Decimal(window)
        result[index + 1] = _rsi_from_averages(average_gain, average_loss)

    return result


def compute_true_range(candles: Sequence[Candle]) -> list[Decimal]:
    if not candles:
        return []

    result: list[Decimal] = [candles[0].range_size]
    for index in range(1, len(candles)):
        current = candles[index]
        previous_close = candles[index - 1].close
        result.append(
            max(
                current.range_size,
                abs(current.high - previous_close),
                abs(current.low - previous_close),
            )
        )
    return result


def compute_atr(candles: Sequence[Candle], window: int = 14) -> list[Decimal | None]:
    _validate_window(window)
    true_ranges = compute_true_range(candles)
    result: list[Decimal | None] = [None] * len(true_ranges)
    if len(true_ranges) < window:
        return result

    atr = sum(true_ranges[:window], start=ZERO) / Decimal(window)
    result[window - 1] = atr

    for index in range(window, len(true_ranges)):
        atr = ((atr * Decimal(window - 1)) + true_ranges[index]) / Decimal(window)
        result[index] = atr

    return result


def _rsi_from_averages(average_gain: Decimal, average_loss: Decimal) -> Decimal:
    if average_loss == ZERO:
        return Decimal("100")
    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def _validate_window(window: int) -> None:
    if window < 1:
        raise ValueError("window must be greater than or equal to 1.")


def _to_decimal(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
