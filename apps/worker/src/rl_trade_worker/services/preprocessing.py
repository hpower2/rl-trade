"""Dataset preprocessing execution helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_data import DatasetVersion, FeatureSet, OHLCCandle, PreprocessingJob, Symbol
from rl_trade_data.models import Timeframe
from rl_trade_features import (
    Candle,
    DatasetRow,
    FeatureSetSpec,
    TimeframeFeaturePoint,
    align_timeframe_features,
    build_dataset,
    compute_atr,
    compute_candle_structure,
    compute_ema,
    compute_rsi,
    compute_sma,
    create_dataset_version,
    detect_candlestick_patterns,
    ensure_feature_set,
    generate_trade_setup_labels,
)

DEFAULT_PRIMARY_TIMEFRAME = Timeframe.M1
DEFAULT_FEATURE_SET_NAME = "baseline_forex"
DEFAULT_FEATURE_SET_VERSION = "v1"
DEFAULT_INDICATOR_WINDOW = 3
DEFAULT_LABEL_HORIZON_BARS = 2
DEFAULT_LABEL_MIN_MOVE_RATIO = Decimal("0.0005")


@dataclass(frozen=True, slots=True)
class CandlePoint:
    timestamp: datetime
    candle: Candle


def perform_preprocessing_job(
    *,
    session: Session,
    job_id: int,
    progress_callback: Callable[[int, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    job = session.get(PreprocessingJob, job_id)
    if job is None:
        raise ValueError(f"Preprocessing job {job_id} does not exist.")

    symbol = session.get(Symbol, job.symbol_id)
    if symbol is None:
        raise ValueError(f"Symbol {job.symbol_id} does not exist.")

    requested_timeframes = resolve_requested_timeframes(job)
    primary_timeframe = resolve_primary_timeframe(job=job, requested_timeframes=requested_timeframes)
    indicator_window = int((job.details or {}).get("indicator_window", DEFAULT_INDICATOR_WINDOW))
    label_horizon_bars = int((job.details or {}).get("label_horizon_bars", DEFAULT_LABEL_HORIZON_BARS))
    label_min_move_ratio = Decimal(str((job.details or {}).get("label_min_move_ratio", DEFAULT_LABEL_MIN_MOVE_RATIO)))

    if progress_callback is not None:
        progress_callback(10, {"phase": "loading_candles"})

    candles_by_timeframe = load_candles_by_timeframe(
        session=session,
        symbol_id=symbol.id,
        requested_timeframes=requested_timeframes,
    )

    if progress_callback is not None:
        progress_callback(35, {"phase": "building_dataset", "primary_timeframe": primary_timeframe.value})

    feature_spec, dataset = build_preprocessing_dataset(
        candles_by_timeframe=candles_by_timeframe,
        primary_timeframe=primary_timeframe,
        requested_timeframes=requested_timeframes,
        indicator_window=indicator_window,
        label_horizon_bars=label_horizon_bars,
        label_min_move_ratio=label_min_move_ratio,
        feature_set_name=str((job.details or {}).get("feature_set_name", DEFAULT_FEATURE_SET_NAME)),
        feature_set_version=str((job.details or {}).get("feature_set_version", DEFAULT_FEATURE_SET_VERSION)),
    )

    if progress_callback is not None:
        progress_callback(75, {"phase": "persisting_dataset", "row_count": dataset.row_count})

    feature_set = ensure_feature_set(session, spec=feature_spec)
    storage_uri = f"dataset://symbol-{symbol.id}/feature-set-{feature_set.id}/{dataset.version_tag}"
    dataset_version = create_dataset_version(
        session,
        symbol_id=symbol.id,
        feature_set_id=feature_set.id,
        dataset=dataset,
        primary_timeframe=primary_timeframe,
        included_timeframes=requested_timeframes,
        storage_uri=storage_uri,
        details={
            "indicator_window": indicator_window,
            "label_horizon_bars": label_horizon_bars,
            "label_min_move_ratio": str(label_min_move_ratio),
        },
    )

    job.feature_set_id = feature_set.id
    job.dataset_version_id = dataset_version.id
    job.details = {
        **(job.details or {}),
        "feature_set_name": feature_spec.name,
        "feature_set_version": feature_spec.version,
        "dataset_version_tag": dataset.version_tag,
        "dataset_storage_uri": storage_uri,
        "row_count": dataset.row_count,
        "primary_timeframe": primary_timeframe.value,
        "included_timeframes": [timeframe.value for timeframe in requested_timeframes],
    }
    session.flush()

    return {
        "job_id": job.id,
        "feature_set_id": feature_set.id,
        "dataset_version_id": dataset_version.id,
        "row_count": dataset.row_count,
        "version_tag": dataset.version_tag,
    }


def load_candles_by_timeframe(
    *,
    session: Session,
    symbol_id: int,
    requested_timeframes: Sequence[Timeframe],
) -> dict[Timeframe, list[CandlePoint]]:
    candles_by_timeframe: dict[Timeframe, list[CandlePoint]] = {}
    for timeframe in requested_timeframes:
        rows = (
            session.execute(
                select(OHLCCandle).where(
                    OHLCCandle.symbol_id == symbol_id,
                    OHLCCandle.timeframe == timeframe,
                ).order_by(OHLCCandle.candle_time)
            )
            .scalars()
            .all()
        )
        if not rows:
            raise ValueError(f"No OHLC candles available for {timeframe.value}.")

        candles_by_timeframe[timeframe] = [
            CandlePoint(
                timestamp=normalize_timestamp(row.candle_time),
                candle=Candle(open=row.open, high=row.high, low=row.low, close=row.close),
            )
            for row in rows
        ]

    return candles_by_timeframe


def build_preprocessing_dataset(
    *,
    candles_by_timeframe: dict[Timeframe, list[CandlePoint]],
    primary_timeframe: Timeframe,
    requested_timeframes: Sequence[Timeframe],
    indicator_window: int,
    label_horizon_bars: int,
    label_min_move_ratio: Decimal,
    feature_set_name: str,
    feature_set_version: str,
) -> tuple[FeatureSetSpec, Any]:
    primary_points = candles_by_timeframe[primary_timeframe]
    primary_candles = [point.candle for point in primary_points]

    sma_values = compute_sma([point.candle.close for point in primary_points], indicator_window)
    ema_values = compute_ema([point.candle.close for point in primary_points], indicator_window)
    rsi_values = compute_rsi([point.candle.close for point in primary_points], indicator_window)
    atr_values = compute_atr(primary_candles, indicator_window)
    structures = [compute_candle_structure(point.candle) for point in primary_points]
    patterns = [detect_candlestick_patterns(primary_candles[max(0, index - 2) : index + 1]) for index in range(len(primary_points))]
    labels = generate_trade_setup_labels(
        primary_candles,
        horizon_bars=label_horizon_bars,
        min_move_ratio=label_min_move_ratio,
    )

    aligned_rows: dict[Timeframe, list[dict[str, Any]]] = {}
    for timeframe in requested_timeframes:
        if timeframe == primary_timeframe:
            continue
        aligned_rows[timeframe] = align_timeframe_features(
            base_timestamps=[point.timestamp for point in primary_points],
            source_points=build_alignment_source_points(candles_by_timeframe[timeframe]),
            prefix=timeframe_feature_prefix(timeframe),
        )

    feature_columns = [
        "close",
        f"sma_{indicator_window}",
        f"ema_{indicator_window}",
        f"rsi_{indicator_window}",
        f"atr_{indicator_window}",
        "body_ratio",
        "upper_shadow_ratio",
        "lower_shadow_ratio",
        "pattern_doji",
        "pattern_hammer",
        "pattern_bullish_engulfing",
        "pattern_bearish_engulfing",
    ]
    for timeframe in requested_timeframes:
        if timeframe == primary_timeframe:
            continue
        prefix = timeframe_feature_prefix(timeframe)
        feature_columns.extend([f"{prefix}_age_seconds", f"{prefix}_trend", f"{prefix}_body_ratio", f"{prefix}_pattern_doji"])

    rows: list[DatasetRow] = []
    for index, point in enumerate(primary_points):
        label = labels[index]
        base_features = {
            "close": point.candle.close,
            f"sma_{indicator_window}": sma_values[index],
            f"ema_{indicator_window}": ema_values[index],
            f"rsi_{indicator_window}": rsi_values[index],
            f"atr_{indicator_window}": atr_values[index],
            "body_ratio": structures[index].body_ratio,
            "upper_shadow_ratio": structures[index].upper_shadow_ratio,
            "lower_shadow_ratio": structures[index].lower_shadow_ratio,
            "pattern_doji": patterns[index].doji,
            "pattern_hammer": patterns[index].hammer,
            "pattern_bullish_engulfing": patterns[index].bullish_engulfing,
            "pattern_bearish_engulfing": patterns[index].bearish_engulfing,
        }

        for timeframe, aligned in aligned_rows.items():
            prefix = timeframe_feature_prefix(timeframe)
            base_features[f"{prefix}_age_seconds"] = aligned[index][f"{prefix}_age_seconds"]
            base_features[f"{prefix}_trend"] = aligned[index][f"{prefix}_trend"]
            base_features[f"{prefix}_body_ratio"] = aligned[index][f"{prefix}_body_ratio"]
            base_features[f"{prefix}_pattern_doji"] = aligned[index][f"{prefix}_pattern_doji"]

        if label is None or any(base_features[column] is None for column in feature_columns):
            continue

        rows.append(
            DatasetRow(
                timestamp=point.timestamp,
                features={column: base_features[column] for column in feature_columns},
                label=label.direction.value,
            )
        )

    if not rows:
        raise ValueError("Preprocessing did not produce any complete dataset rows.")

    feature_spec = FeatureSetSpec(
        name=feature_set_name,
        version=feature_set_version,
        description="Baseline deterministic preprocessing feature set.",
        feature_columns=feature_columns,
        indicator_columns=[f"sma_{indicator_window}", f"ema_{indicator_window}", f"rsi_{indicator_window}", f"atr_{indicator_window}"],
        pattern_columns=["pattern_doji", "pattern_hammer", "pattern_bullish_engulfing", "pattern_bearish_engulfing"],
        parameters={
            "indicator_window": indicator_window,
            "label_horizon_bars": label_horizon_bars,
            "label_min_move_ratio": str(label_min_move_ratio),
            "primary_timeframe": primary_timeframe.value,
            "included_timeframes": [timeframe.value for timeframe in requested_timeframes],
        },
    )
    dataset = build_dataset(rows=rows, label_name="direction", feature_columns=feature_columns)
    return feature_spec, dataset


def build_alignment_source_points(points: Sequence[CandlePoint]) -> list[TimeframeFeaturePoint]:
    source_points: list[TimeframeFeaturePoint] = []
    candles = [point.candle for point in points]
    for index, point in enumerate(points):
        pattern_set = detect_candlestick_patterns(candles[max(0, index - 2) : index + 1])
        structure = compute_candle_structure(point.candle)
        source_points.append(
            TimeframeFeaturePoint(
                timestamp=point.timestamp,
                values={
                    "trend": structure.direction,
                    "body_ratio": structure.body_ratio,
                    "pattern_doji": pattern_set.doji,
                },
            )
        )
    return source_points


def resolve_requested_timeframes(job: PreprocessingJob) -> list[Timeframe]:
    requested = [Timeframe(value) for value in job.requested_timeframes] if job.requested_timeframes else [Timeframe.M1, Timeframe.M5, Timeframe.M15]
    ordered: list[Timeframe] = []
    seen: set[Timeframe] = set()
    for timeframe in requested:
        if timeframe in seen:
            continue
        seen.add(timeframe)
        ordered.append(timeframe)
    return ordered


def resolve_primary_timeframe(*, job: PreprocessingJob, requested_timeframes: Sequence[Timeframe]) -> Timeframe:
    configured = (job.details or {}).get("primary_timeframe")
    primary = Timeframe(configured) if configured is not None else DEFAULT_PRIMARY_TIMEFRAME
    if primary not in requested_timeframes:
        raise ValueError(f"Primary timeframe {primary.value} must be present in requested_timeframes.")
    return primary


def normalize_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def timeframe_feature_prefix(timeframe: Timeframe) -> str:
    return f"m{timeframe.value[:-1]}"
