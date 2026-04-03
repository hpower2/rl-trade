"""Feature engineering primitives."""

from rl_trade_features.alignment import TimeframeFeaturePoint, align_timeframe_features
from rl_trade_features.datasets import (
    BuiltDataset,
    DatasetRow,
    FeatureSetSpec,
    build_dataset,
    create_dataset_version,
    ensure_feature_set,
)
from rl_trade_features.indicators import compute_atr, compute_ema, compute_rsi, compute_sma, compute_true_range
from rl_trade_features.labels import (
    DirectionLabel,
    ForwardReturnLabel,
    TradeSetupLabel,
    generate_forward_return_labels,
    generate_trade_setup_labels,
)
from rl_trade_features.patterns import Candle, CandlestickPatternSet, detect_candlestick_patterns
from rl_trade_features.structure import CandleStructure, compute_candle_structure

__all__ = [
    "BuiltDataset",
    "Candle",
    "CandleStructure",
    "CandlestickPatternSet",
    "DatasetRow",
    "DirectionLabel",
    "FeatureSetSpec",
    "ForwardReturnLabel",
    "TimeframeFeaturePoint",
    "TradeSetupLabel",
    "align_timeframe_features",
    "build_dataset",
    "compute_atr",
    "compute_candle_structure",
    "compute_ema",
    "compute_rsi",
    "compute_sma",
    "compute_true_range",
    "create_dataset_version",
    "detect_candlestick_patterns",
    "ensure_feature_set",
    "generate_forward_return_labels",
    "generate_trade_setup_labels",
]
