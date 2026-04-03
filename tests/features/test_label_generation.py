"""Label generation and leakage guard tests."""

from __future__ import annotations

from decimal import Decimal

from rl_trade_features import Candle, DirectionLabel, generate_forward_return_labels, generate_trade_setup_labels


def candle(open_price: str, high_price: str, low_price: str, close_price: str) -> Candle:
    return Candle(open=open_price, high=high_price, low=low_price, close=close_price)


def test_generate_forward_return_labels_uses_exact_future_horizon() -> None:
    labels = generate_forward_return_labels(
        [
            candle("1.1000", "1.1010", "1.0990", "1.1000"),
            candle("1.1000", "1.1020", "1.0990", "1.1010"),
            candle("1.1010", "1.1040", "1.1000", "1.1030"),
            candle("1.1030", "1.1050", "1.1020", "1.1040"),
        ],
        horizon_bars=2,
    )

    assert labels[0] is not None
    assert labels[0].future_close == Decimal("1.1030")
    assert labels[0].return_ratio == Decimal("0.002727272727272727272727272727")
    assert labels[2] is None
    assert labels[3] is None


def test_generate_trade_setup_labels_emits_buy_sell_and_no_trade() -> None:
    buy_labels = generate_trade_setup_labels(
        [
            candle("1.1000", "1.1010", "1.0990", "1.1000"),
            candle("1.1000", "1.1060", "1.0995", "1.1050"),
            candle("1.1050", "1.1070", "1.1040", "1.1060"),
        ],
        horizon_bars=2,
        min_move_ratio="0.002",
    )
    sell_labels = generate_trade_setup_labels(
        [
            candle("1.1000", "1.1010", "1.0990", "1.1000"),
            candle("1.1000", "1.1005", "1.0940", "1.0950"),
            candle("1.0950", "1.0960", "1.0920", "1.0930"),
        ],
        horizon_bars=2,
        min_move_ratio="0.002",
    )
    flat_labels = generate_trade_setup_labels(
        [
            candle("1.1000", "1.1010", "1.0990", "1.1000"),
            candle("1.1000", "1.1010", "1.0995", "1.1005"),
            candle("1.1005", "1.1010", "1.1000", "1.1004"),
        ],
        horizon_bars=2,
        min_move_ratio="0.003",
    )

    assert buy_labels[0] is not None
    assert buy_labels[0].direction is DirectionLabel.BUY
    assert sell_labels[0] is not None
    assert sell_labels[0].direction is DirectionLabel.SELL
    assert flat_labels[0] is not None
    assert flat_labels[0].direction is DirectionLabel.NO_TRADE


def test_trade_setup_labels_do_not_leak_beyond_requested_horizon() -> None:
    baseline = generate_trade_setup_labels(
        [
            candle("1.1000", "1.1010", "1.0990", "1.1000"),
            candle("1.1000", "1.1040", "1.0995", "1.1030"),
            candle("1.1030", "1.1050", "1.1020", "1.1040"),
            candle("1.1040", "1.1200", "1.1030", "1.1190"),
        ],
        horizon_bars=2,
        min_move_ratio="0.001",
    )
    mutated = generate_trade_setup_labels(
        [
            candle("1.1000", "1.1010", "1.0990", "1.1000"),
            candle("1.1000", "1.1040", "1.0995", "1.1030"),
            candle("1.1030", "1.1050", "1.1020", "1.1040"),
            candle("1.1040", "1.3000", "1.0000", "1.2500"),
        ],
        horizon_bars=2,
        min_move_ratio="0.001",
    )

    assert baseline[0] == mutated[0]
    assert baseline[1] != mutated[1]


def test_trade_setup_labels_leave_trailing_horizon_unlabeled() -> None:
    labels = generate_trade_setup_labels(
        [
            candle("1.1000", "1.1010", "1.0990", "1.1000"),
            candle("1.1000", "1.1020", "1.0990", "1.1010"),
            candle("1.1010", "1.1030", "1.1000", "1.1020"),
        ],
        horizon_bars=2,
    )

    assert labels == [labels[0], None, None]
