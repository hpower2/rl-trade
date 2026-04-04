"""Manual smoke path for live ingestion and training WebSocket updates."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import TextIO
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.routes.events import router as events_router
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings
from rl_trade_data import (
    Base,
    DatasetVersion,
    FeatureSet,
    IngestionJob,
    JobStatus,
    OHLCCandle,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import DatasetStatus, Timeframe, TrainingType
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.tasks import run_ingestion_job, run_supervised_training_job
from rl_trade_trading import MT5CandleRecord


@dataclass(frozen=True, slots=True)
class WebSocketEventDryRunSummary:
    ingestion_event_count: int
    ingestion_statuses: tuple[str, ...]
    ingestion_final_status: str
    training_event_count: int
    training_statuses: tuple[str, ...]
    training_final_status: str


class DryRunMT5Gateway:
    def fetch_candles(
        self,
        settings: Settings,
        *,
        symbol_code: str,
        timeframe: Timeframe,
        start_time: datetime,
        count: int,
    ) -> list[MT5CandleRecord]:
        del settings, symbol_code, start_time, count
        if timeframe is Timeframe.M1:
            points = [
                (datetime(2026, 1, 2, 0, 0, tzinfo=UTC), Decimal("1.1040")),
                (datetime(2026, 1, 2, 0, 1, tzinfo=UTC), Decimal("1.1045")),
            ]
        elif timeframe is Timeframe.M5:
            points = [(datetime(2026, 1, 2, 0, 0, tzinfo=UTC), Decimal("1.1048"))]
        else:
            points = [(datetime(2026, 1, 2, 0, 0, tzinfo=UTC), Decimal("1.1052"))]

        candles: list[MT5CandleRecord] = []
        for candle_time, close in points:
            open_price = close - Decimal("0.0002")
            candles.append(
                MT5CandleRecord(
                    timeframe=timeframe,
                    candle_time=candle_time,
                    open=open_price,
                    high=close + Decimal("0.0003"),
                    low=open_price - Decimal("0.0003"),
                    close=close,
                    volume=Decimal("100"),
                    spread=10,
                )
            )
        return candles


def run_dry_run(*, stdout: TextIO | None = None) -> WebSocketEventDryRunSummary:
    output = stdout
    with TemporaryDirectory(prefix="rl-trade-websocket-events-") as temp_dir:
        workspace = Path(temp_dir)
        client = _build_client(database_path=workspace / "websocket_event_dry_run.sqlite")

        with _patched_worker_runtime(
            session_factory=client.app.state.session_factory,
            settings=Settings(_env_file=None, artifacts_root_dir=str(workspace / ".artifacts")),
            event_broadcaster=client.app.state.event_broadcaster,
        ):
            with client.websocket_connect("/ws/events?topics=ingestion_progress,training_progress") as websocket:
                run_ingestion_job.delay(job_id=client.app.state.ingestion_job_id)
                ingestion_messages = _collect_messages(websocket, expected_event_type="ingestion_progress", terminal_status="succeeded")
                _write(output, f"ingestion statuses={','.join(_statuses(ingestion_messages))}")

                run_supervised_training_job.delay(job_id=client.app.state.training_job_id)
                training_messages = _collect_messages(websocket, expected_event_type="training_progress", terminal_status="succeeded")
                _write(output, f"training statuses={','.join(_statuses(training_messages))}")

        return WebSocketEventDryRunSummary(
            ingestion_event_count=len(ingestion_messages),
            ingestion_statuses=tuple(_statuses(ingestion_messages)),
            ingestion_final_status=_statuses(ingestion_messages)[-1],
            training_event_count=len(training_messages),
            training_statuses=tuple(_statuses(training_messages)),
            training_final_status=_statuses(training_messages)[-1],
        )


def run_cli() -> int:
    summary = run_dry_run(stdout=sys.stdout)
    print("WebSocket event dry run completed.")
    print(
        "summary "
        f"ingestion_event_count={summary.ingestion_event_count} "
        f"ingestion_final_status={summary.ingestion_final_status} "
        f"training_event_count={summary.training_event_count} "
        f"training_final_status={summary.training_final_status}"
    )
    return 0


def _build_client(*, database_path: Path) -> TestClient:
    database_url = f"sqlite+pysqlite:///{database_path}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol_id, ingestion_job_id = _seed_ingestion_job(session)
        training_job_id = _seed_training_job(session, symbol_id=symbol_id)

    app = FastAPI()
    app.include_router(events_router)
    app.state.settings = Settings(_env_file=None)
    app.state.event_broadcaster = EventBroadcaster()
    app.state.session_factory = session_factory
    app.state.ingestion_job_id = ingestion_job_id
    app.state.training_job_id = training_job_id
    return TestClient(app)


def _seed_ingestion_job(session) -> tuple[int, int]:
    symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
    session.add(symbol)
    session.flush()
    job = IngestionJob(
        symbol_id=symbol.id,
        requested_timeframes=["1m", "5m", "15m"],
        details={"lookback_bars": 24},
    )
    session.add(job)
    session.flush()
    return symbol.id, job.id


def _seed_training_job(session, *, symbol_id: int) -> int:
    feature_set = FeatureSet(name="baseline_forex", version="v1", feature_columns=["close"])
    session.add(feature_set)
    session.flush()
    dataset_version = DatasetVersion(
        symbol_id=symbol_id,
        feature_set_id=feature_set.id,
        status=DatasetStatus.READY,
        version_tag="websocket-live-demo",
        primary_timeframe=Timeframe.M1,
        included_timeframes=["1m", "5m", "15m"],
        label_name="trade_setup_direction",
        row_count=16,
        data_hash="websocket-demo-hash",
        details={
            "indicator_window": 3,
            "label_horizon_bars": 2,
            "label_min_move_ratio": "0.0005",
        },
    )
    session.add(dataset_version)
    session.flush()
    training_request = TrainingRequest(
        symbol_id=symbol_id,
        dataset_version_id=dataset_version.id,
        training_type=TrainingType.SUPERVISED,
        requested_timeframes=["1m", "5m", "15m"],
    )
    session.add(training_request)
    session.flush()
    training_job = SupervisedTrainingJob(
        training_request_id=training_request.id,
        dataset_version_id=dataset_version.id,
        status=JobStatus.PENDING,
        algorithm="auto_baseline",
        hyperparameters={
            "model_name": "baseline_classifier",
            "validation_ratio": 0.25,
            "walk_forward_folds": 2,
        },
    )
    session.add(training_job)
    session.flush()
    _seed_training_candles(session, symbol_id=symbol_id)
    return training_job.id


def _seed_training_candles(session, *, symbol_id: int) -> None:
    base_time = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    m1_closes = [
        Decimal("1.1000"),
        Decimal("1.1004"),
        Decimal("1.1008"),
        Decimal("1.1012"),
        Decimal("1.1016"),
        Decimal("1.1020"),
        Decimal("1.1024"),
        Decimal("1.1028"),
        Decimal("1.1032"),
        Decimal("1.1036"),
        Decimal("1.1040"),
        Decimal("1.1044"),
    ]

    for index, close in enumerate(m1_closes):
        open_price = close - Decimal("0.0002")
        session.add(
            OHLCCandle(
                symbol_id=symbol_id,
                timeframe=Timeframe.M1,
                candle_time=base_time + timedelta(minutes=index),
                open=open_price,
                high=close + Decimal("0.0003"),
                low=open_price - Decimal("0.0003"),
                close=close,
                volume=Decimal("100") + Decimal(index),
                provider="mt5",
                source="historical",
            )
        )
        session.flush()

    for minute_offset, open_price, close in [
        (0, Decimal("1.1000"), Decimal("1.1016")),
        (5, Decimal("1.1016"), Decimal("1.1036")),
        (10, Decimal("1.1036"), Decimal("1.1044")),
    ]:
        session.add(
            OHLCCandle(
                symbol_id=symbol_id,
                timeframe=Timeframe.M5,
                candle_time=base_time + timedelta(minutes=minute_offset),
                open=open_price,
                high=close + Decimal("0.0004"),
                low=open_price - Decimal("0.0004"),
                close=close,
                volume=Decimal("250"),
                provider="mt5",
                source="historical",
            )
        )
        session.flush()

    session.add(
        OHLCCandle(
            symbol_id=symbol_id,
            timeframe=Timeframe.M15,
            candle_time=base_time,
            open=Decimal("1.0995"),
            high=Decimal("1.1048"),
            low=Decimal("1.0990"),
            close=Decimal("1.1044"),
            volume=Decimal("500"),
            provider="mt5",
            source="historical",
        )
    )
    session.flush()


def _collect_messages(
    websocket,
    *,
    expected_event_type: str,
    terminal_status: str,
) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    for _ in range(12):
        message = websocket.receive_json()
        if message["event"]["event_type"] != expected_event_type:
            continue
        messages.append(message)
        if message["event"]["payload"]["status"] == terminal_status:
            break

    if not messages or messages[-1]["event"]["payload"]["status"] != terminal_status:
        raise RuntimeError(f"Did not receive terminal {expected_event_type} status {terminal_status}.")

    return messages


def _statuses(messages: list[dict[str, object]]) -> list[str]:
    return [str(message["event"]["payload"]["status"]) for message in messages]


@contextmanager
def _patched_worker_runtime(
    *,
    session_factory,
    settings: Settings,
    event_broadcaster: EventBroadcaster,
) -> Iterator[None]:
    original_always_eager = celery_app.conf.task_always_eager
    original_eager_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    with ExitStack() as stack:
        stack.enter_context(patch("rl_trade_worker.tasks.get_session_factory", lambda: session_factory))
        stack.enter_context(patch("rl_trade_worker.task_base.get_session_factory", lambda: session_factory))
        stack.enter_context(patch("rl_trade_worker.tasks.get_settings", lambda: settings))
        stack.enter_context(patch("rl_trade_worker.tasks.MT5Gateway", DryRunMT5Gateway))
        stack.enter_context(patch("rl_trade_worker.task_base.get_event_publisher", lambda: event_broadcaster))
        try:
            yield
        finally:
            celery_app.conf.task_always_eager = original_always_eager
            celery_app.conf.task_eager_propagates = original_eager_propagates


def _write(stdout: TextIO | None, message: str) -> None:
    if stdout is not None:
        stdout.write(f"{message}\n")


if __name__ == "__main__":
    raise SystemExit(run_cli())
