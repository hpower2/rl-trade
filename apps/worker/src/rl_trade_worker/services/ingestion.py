"""OHLC ingestion execution helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rl_trade_common import Settings
from rl_trade_data import IngestionJob, OHLCCandle, Symbol
from rl_trade_data.models.enums import Timeframe
from rl_trade_trading import MT5CandleRecord, MT5Gateway

DEFAULT_LOOKBACK_BARS = 500
TIMEFRAME_PROGRESS_KEY = "timeframe_progress"
COMPLETED_TIMEFRAMES_KEY = "completed_timeframes"
RESUME_PENDING_TIMEFRAMES_KEY = "resume_pending_timeframes"


def perform_ingestion_job(
    *,
    session: Session,
    gateway: MT5Gateway,
    settings: Settings,
    job_id: int,
    progress_callback: Callable[[int, dict[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise ValueError(f"Ingestion job {job_id} does not exist.")

    symbol = session.get(Symbol, job.symbol_id)
    if symbol is None:
        raise ValueError(f"Symbol {job.symbol_id} does not exist.")

    timeframes = [Timeframe(value) for value in job.requested_timeframes]
    if not timeframes:
        raise ValueError("Ingestion job must include at least one timeframe.")

    resumable_timeframes = get_resumable_timeframes(job=job, timeframes=timeframes)
    lookback_bars = int((job.details or {}).get("lookback_bars", DEFAULT_LOOKBACK_BARS))
    total_requested = 0
    total_written = 0
    latest_candle_time: datetime | None = None

    for index, timeframe in enumerate(resumable_timeframes, start=1):
        if progress_callback is not None:
            progress_callback(
                min(90, int((index - 1) / max(len(resumable_timeframes), 1) * 90) + 5),
                {"phase": "fetching", "timeframe": timeframe.value},
            )

        start_time = resolve_ingestion_start_time(
            session=session,
            symbol_id=symbol.id,
            timeframe=timeframe,
            sync_mode=job.sync_mode,
            lookback_bars=lookback_bars,
        )
        record_timeframe_progress(
            job=job,
            timeframe=timeframe,
            updates={
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
                "start_time": start_time.isoformat(),
            },
        )
        session.flush()

        try:
            candles = gateway.fetch_candles(
                settings,
                symbol_code=symbol.code,
                timeframe=timeframe,
                start_time=start_time,
                count=lookback_bars,
            )
            total_requested += len(candles)

            inserted_count, timeframe_latest = persist_candles(
                session=session,
                symbol_id=symbol.id,
                timeframe=timeframe,
                candles=candles,
                source_provider=job.source_provider,
            )
            total_written += inserted_count
            if timeframe_latest is not None and (latest_candle_time is None or timeframe_latest > latest_candle_time):
                latest_candle_time = timeframe_latest

            record_timeframe_progress(
                job=job,
                timeframe=timeframe,
                updates={
                    "status": "succeeded",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "requested": len(candles),
                    "written": inserted_count,
                    "last_completed_candle_time": timeframe_latest.isoformat() if timeframe_latest else None,
                },
            )
            session.flush()

            if progress_callback is not None:
                progress_callback(
                    min(95, int(index / max(len(resumable_timeframes), 1) * 90)),
                    {
                        "phase": "persisted",
                        "timeframe": timeframe.value,
                        "requested": len(candles),
                        "written": inserted_count,
                    },
                )
        except Exception as exc:
            record_timeframe_progress(
                job=job,
                timeframe=timeframe,
                updates={
                    "status": "failed",
                    "failed_at": datetime.now(UTC).isoformat(),
                    "error_message": str(exc),
                },
            )
            job.details = {
                **(job.details or {}),
                RESUME_PENDING_TIMEFRAMES_KEY: [
                    pending_timeframe.value for pending_timeframe in resumable_timeframes[index - 1 :]
                ],
            }
            session.flush()
            raise

    job.candles_requested = total_requested
    job.candles_written = total_written
    job.last_successful_candle_time = latest_candle_time
    job.details = {
        **(job.details or {}),
        "ingested_timeframes": [timeframe.value for timeframe in timeframes],
        COMPLETED_TIMEFRAMES_KEY: get_completed_timeframes(job),
        RESUME_PENDING_TIMEFRAMES_KEY: [],
    }
    session.flush()

    return {
        "job_id": job.id,
        "candles_requested": total_requested,
        "candles_written": total_written,
        "last_successful_candle_time": latest_candle_time.isoformat() if latest_candle_time else None,
    }


def resolve_ingestion_start_time(
    *,
    session: Session,
    symbol_id: int,
    timeframe: Timeframe,
    sync_mode: str,
    lookback_bars: int,
) -> datetime:
    existing_max_time = session.scalar(
        select(func.max(OHLCCandle.candle_time)).where(
            OHLCCandle.symbol_id == symbol_id,
            OHLCCandle.timeframe == timeframe,
        )
    )
    if existing_max_time is not None and existing_max_time.tzinfo is None:
        existing_max_time = existing_max_time.replace(tzinfo=UTC)

    if sync_mode == "incremental" and existing_max_time is not None:
        return existing_max_time + timeframe_delta(timeframe)

    return datetime.now(UTC) - timeframe_delta(timeframe) * lookback_bars


def persist_candles(
    *,
    session: Session,
    symbol_id: int,
    timeframe: Timeframe,
    candles: list[MT5CandleRecord],
    source_provider: str,
) -> tuple[int, datetime | None]:
    if not candles:
        return 0, None

    existing_times = {
        normalize_utc_timestamp(existing_time)
        for existing_time in session.execute(
            select(OHLCCandle.candle_time).where(
                OHLCCandle.symbol_id == symbol_id,
                OHLCCandle.timeframe == timeframe,
                OHLCCandle.candle_time.in_([candle.candle_time for candle in candles]),
            )
        )
        .scalars()
        .all()
    }

    inserted = 0
    latest_time: datetime | None = None
    for candle in candles:
        latest_time = candle.candle_time if latest_time is None or candle.candle_time > latest_time else latest_time
        if candle.candle_time in existing_times:
            continue

        session.add(
            OHLCCandle(
                symbol_id=symbol_id,
                timeframe=timeframe,
                candle_time=candle.candle_time,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                spread=candle.spread,
                provider=source_provider,
                source="historical",
            )
        )
        session.flush()
        inserted += 1

    return inserted, latest_time


def timeframe_delta(timeframe: Timeframe) -> timedelta:
    mapping = {
        Timeframe.M1: timedelta(minutes=1),
        Timeframe.M5: timedelta(minutes=5),
        Timeframe.M15: timedelta(minutes=15),
    }
    return mapping[timeframe]


def get_resumable_timeframes(*, job: IngestionJob, timeframes: list[Timeframe]) -> list[Timeframe]:
    timeframe_progress = dict((job.details or {}).get(TIMEFRAME_PROGRESS_KEY, {}))
    resumable: list[Timeframe] = []
    for timeframe in timeframes:
        if timeframe_progress.get(timeframe.value, {}).get("status") == "succeeded":
            continue
        resumable.append(timeframe)
    return resumable


def get_completed_timeframes(job: IngestionJob) -> list[str]:
    timeframe_progress = dict((job.details or {}).get(TIMEFRAME_PROGRESS_KEY, {}))
    return [
        timeframe
        for timeframe, state in timeframe_progress.items()
        if isinstance(state, dict) and state.get("status") == "succeeded"
    ]


def record_timeframe_progress(
    *,
    job: IngestionJob,
    timeframe: Timeframe,
    updates: dict[str, Any],
) -> None:
    details = dict(job.details or {})
    timeframe_progress = dict(details.get(TIMEFRAME_PROGRESS_KEY, {}))
    current_state = dict(timeframe_progress.get(timeframe.value, {}))
    current_state.update(updates)
    timeframe_progress[timeframe.value] = current_state
    details[TIMEFRAME_PROGRESS_KEY] = timeframe_progress
    details[COMPLETED_TIMEFRAMES_KEY] = get_completed_timeframes_from_progress(timeframe_progress)
    details[RESUME_PENDING_TIMEFRAMES_KEY] = [
        name
        for name, state in timeframe_progress.items()
        if isinstance(state, dict) and state.get("status") != "succeeded"
    ]
    job.details = details


def get_completed_timeframes_from_progress(timeframe_progress: dict[str, Any]) -> list[str]:
    return [
        timeframe
        for timeframe, state in timeframe_progress.items()
        if isinstance(state, dict) and state.get("status") == "succeeded"
    ]


def normalize_utc_timestamp(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
