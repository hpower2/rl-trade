"""Deterministic dataset versioning helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from rl_trade_data import DatasetVersion, FeatureSet
from rl_trade_data.models import DatasetStatus, Timeframe

DatasetValue = str | int | float | bool | None | Decimal | Enum


@dataclass(frozen=True, slots=True)
class FeatureSetSpec:
    name: str
    version: str
    description: str | None = None
    feature_columns: Sequence[str] = ()
    indicator_columns: Sequence[str] = ()
    pattern_columns: Sequence[str] = ()
    parameters: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class DatasetRow:
    timestamp: datetime
    features: Mapping[str, DatasetValue]
    label: DatasetValue

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _normalize_timestamp(self.timestamp))
        object.__setattr__(self, "features", dict(self.features))


@dataclass(frozen=True, slots=True)
class BuiltDataset:
    label_name: str
    feature_columns: tuple[str, ...]
    rows: tuple[DatasetRow, ...]
    row_count: int
    data_hash: str
    version_tag: str
    candle_start_time: datetime | None
    candle_end_time: datetime | None


def build_dataset(
    *,
    rows: Sequence[DatasetRow],
    label_name: str,
    feature_columns: Sequence[str] | None = None,
) -> BuiltDataset:
    normalized_rows = tuple(rows)
    normalized_columns = tuple(feature_columns or _collect_feature_columns(normalized_rows))
    payload_rows = [
        {
            "timestamp": row.timestamp.isoformat(),
            "features": {column: _stable_json_value(row.features.get(column)) for column in normalized_columns},
            "label": _stable_json_value(row.label),
        }
        for row in normalized_rows
    ]
    payload = {
        "label_name": label_name,
        "feature_columns": list(normalized_columns),
        "rows": payload_rows,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    data_hash = hashlib.sha256(payload_bytes).hexdigest()

    return BuiltDataset(
        label_name=label_name,
        feature_columns=normalized_columns,
        rows=normalized_rows,
        row_count=len(normalized_rows),
        data_hash=data_hash,
        version_tag=f"{label_name}-{data_hash[:12]}",
        candle_start_time=normalized_rows[0].timestamp if normalized_rows else None,
        candle_end_time=normalized_rows[-1].timestamp if normalized_rows else None,
    )


def ensure_feature_set(session: Session, *, spec: FeatureSetSpec) -> FeatureSet:
    feature_set = session.scalar(
        select(FeatureSet).where(
            FeatureSet.name == spec.name,
            FeatureSet.version == spec.version,
        )
    )
    if feature_set is None:
        feature_set = FeatureSet(name=spec.name, version=spec.version)
        session.add(feature_set)

    feature_set.description = spec.description
    feature_set.feature_columns = list(spec.feature_columns)
    feature_set.indicator_columns = list(spec.indicator_columns)
    feature_set.pattern_columns = list(spec.pattern_columns)
    feature_set.parameters = dict(spec.parameters or {})
    session.flush()
    return feature_set


def create_dataset_version(
    session: Session,
    *,
    symbol_id: int,
    feature_set_id: int,
    dataset: BuiltDataset,
    primary_timeframe: Timeframe,
    included_timeframes: Sequence[Timeframe],
    storage_uri: str | None = None,
    status: DatasetStatus = DatasetStatus.READY,
    details: Mapping[str, Any] | None = None,
) -> DatasetVersion:
    dataset_version = session.scalar(
        select(DatasetVersion).where(
            DatasetVersion.symbol_id == symbol_id,
            DatasetVersion.feature_set_id == feature_set_id,
            DatasetVersion.version_tag == dataset.version_tag,
        )
    )
    if dataset_version is None:
        dataset_version = DatasetVersion(
            symbol_id=symbol_id,
            feature_set_id=feature_set_id,
            version_tag=dataset.version_tag,
        )
        session.add(dataset_version)

    dataset_version.status = status
    dataset_version.primary_timeframe = primary_timeframe
    dataset_version.included_timeframes = [timeframe.value for timeframe in included_timeframes]
    dataset_version.label_name = dataset.label_name
    dataset_version.row_count = dataset.row_count
    dataset_version.data_hash = dataset.data_hash
    dataset_version.storage_uri = storage_uri
    dataset_version.candle_start_time = dataset.candle_start_time
    dataset_version.candle_end_time = dataset.candle_end_time
    dataset_version.details = {
        "feature_columns": list(dataset.feature_columns),
        **dict(details or {}),
    }
    session.flush()
    return dataset_version


def _collect_feature_columns(rows: Sequence[DatasetRow]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row.features:
            if column in seen:
                continue
            seen.add(column)
            ordered.append(column)
    return ordered


def _normalize_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _stable_json_value(value: DatasetValue) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value
