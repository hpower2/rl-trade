"""Deterministic multi-timeframe alignment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping, Sequence

FeatureValue = DecimalValue = int | float | str | bool | None


@dataclass(frozen=True, slots=True)
class TimeframeFeaturePoint:
    timestamp: datetime
    values: Mapping[str, FeatureValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _normalize_timestamp(self.timestamp))
        object.__setattr__(self, "values", dict(self.values))


def align_timeframe_features(
    *,
    base_timestamps: Sequence[datetime],
    source_points: Sequence[TimeframeFeaturePoint],
    prefix: str,
    max_age: timedelta | None = None,
) -> list[dict[str, FeatureValue]]:
    normalized_base = [_normalize_timestamp(timestamp) for timestamp in base_timestamps]
    normalized_source = sorted(source_points, key=lambda point: point.timestamp)
    value_keys = _collect_value_keys(normalized_source)
    aligned_rows: list[dict[str, FeatureValue]] = []
    source_index = 0
    active_point: TimeframeFeaturePoint | None = None

    for timestamp in normalized_base:
        while source_index < len(normalized_source) and normalized_source[source_index].timestamp <= timestamp:
            active_point = normalized_source[source_index]
            source_index += 1

        aligned_rows.append(
            _build_aligned_row(
                timestamp=timestamp,
                active_point=active_point,
                prefix=prefix,
                value_keys=value_keys,
                max_age=max_age,
            )
        )

    return aligned_rows


def _build_aligned_row(
    *,
    timestamp: datetime,
    active_point: TimeframeFeaturePoint | None,
    prefix: str,
    value_keys: Sequence[str],
    max_age: timedelta | None,
) -> dict[str, FeatureValue]:
    row: dict[str, FeatureValue] = {
        f"{prefix}_timestamp": None,
        f"{prefix}_age_seconds": None,
    }
    for key in value_keys:
        row[f"{prefix}_{key}"] = None

    if active_point is None:
        return row

    age = timestamp - active_point.timestamp
    if age < timedelta(0):
        return row
    if max_age is not None and age > max_age:
        return row

    row[f"{prefix}_timestamp"] = active_point.timestamp.isoformat()
    row[f"{prefix}_age_seconds"] = int(age.total_seconds())
    for key in value_keys:
        row[f"{prefix}_{key}"] = active_point.values.get(key)
    return row


def _collect_value_keys(source_points: Sequence[TimeframeFeaturePoint]) -> list[str]:
    ordered_keys: list[str] = []
    seen: set[str] = set()
    for point in source_points:
        for key in point.values:
            if key in seen:
                continue
            seen.add(key)
            ordered_keys.append(key)
    return ordered_keys


def _normalize_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
