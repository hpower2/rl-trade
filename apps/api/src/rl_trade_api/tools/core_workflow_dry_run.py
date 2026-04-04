"""Manual dry-run smoke path for the core validate-to-paper-trade workflow."""

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

try:
    from rl_trade_api.api.deps import get_api_settings, get_db_session, get_mt5_gateway, require_authenticated_principal
    from rl_trade_api.api.router import router as api_router
    from rl_trade_api.core.errors import register_exception_handlers
    from rl_trade_api.services.auth import AuthPrincipal
    from rl_trade_api.services.events import EventBroadcaster
    from rl_trade_common.settings import Settings
    from rl_trade_data import Base, IngestionJob, build_engine, build_session_factory, session_scope
    from rl_trade_data.models import ConnectionStatus, Timeframe
    from rl_trade_trading import (
        MT5CandleRecord,
        MT5ConnectionState,
        MT5HistoricalOrderRecord,
        MT5OrderResult,
        MT5PositionRecord,
        SymbolValidationDecision,
    )
    from rl_trade_worker.celery_app import celery_app
except ModuleNotFoundError:  # pragma: no cover - repo-local script fallback
    repo_root = Path(__file__).resolve().parents[5]
    sys.path.insert(0, str(repo_root / "apps" / "api" / "src"))
    sys.path.insert(0, str(repo_root / "apps" / "worker" / "src"))
    sys.path.insert(0, str(repo_root / "libs" / "common" / "src"))
    sys.path.insert(0, str(repo_root / "libs" / "data" / "src"))
    sys.path.insert(0, str(repo_root / "libs" / "features" / "src"))
    sys.path.insert(0, str(repo_root / "libs" / "ml" / "src"))
    sys.path.insert(0, str(repo_root / "libs" / "trading" / "src"))
    from rl_trade_api.api.deps import get_api_settings, get_db_session, get_mt5_gateway, require_authenticated_principal
    from rl_trade_api.api.router import router as api_router
    from rl_trade_api.core.errors import register_exception_handlers
    from rl_trade_api.services.auth import AuthPrincipal
    from rl_trade_api.services.events import EventBroadcaster
    from rl_trade_common.settings import Settings
    from rl_trade_data import Base, IngestionJob, build_engine, build_session_factory, session_scope
    from rl_trade_data.models import ConnectionStatus, Timeframe
    from rl_trade_trading import (
        MT5CandleRecord,
        MT5ConnectionState,
        MT5HistoricalOrderRecord,
        MT5OrderResult,
        MT5PositionRecord,
        SymbolValidationDecision,
    )
    from rl_trade_worker.celery_app import celery_app


@dataclass(frozen=True, slots=True)
class CoreWorkflowDryRunSummary:
    symbol_code: str
    ingestion_status: str
    candles_written: int
    preprocessing_status: str
    dataset_version_id: int
    training_status: str
    model_id: int
    evaluation_approved: bool
    approved_symbol_count: int
    runtime_enabled: bool
    signal_status: str
    order_status: str
    sync_orders_updated: int
    sync_positions_updated: int
    open_position_count: int
    stopped: bool


class DryRunMT5Gateway:
    def __init__(self) -> None:
        self._submitted_comments: list[str] = []

    def validate_symbol(self, settings: Settings, requested_symbol: str) -> SymbolValidationDecision:
        del settings
        normalized = requested_symbol.strip().upper().replace("/", "")
        if normalized != "EURUSD":
            raise ValueError(f"unsupported dry-run symbol: {requested_symbol}")
        return SymbolValidationDecision(
            requested_symbol=requested_symbol,
            normalized_input=normalized,
            normalized_symbol="EURUSD",
            provider="mt5",
            is_valid=True,
            base_currency="EUR",
            quote_currency="USD",
            details={"matched_by": "dry_run_fixture"},
        )

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
        base_time = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
        if timeframe is Timeframe.M1:
            closes = [
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
            points = [(base_time + timedelta(minutes=index), close) for index, close in enumerate(closes)]
        elif timeframe is Timeframe.M5:
            points = [
                (base_time + timedelta(minutes=0), Decimal("1.1016")),
                (base_time + timedelta(minutes=5), Decimal("1.1036")),
                (base_time + timedelta(minutes=10), Decimal("1.1044")),
            ]
        else:
            points = [(base_time, Decimal("1.1044"))]

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

    def get_connection_state(self, settings: Settings) -> MT5ConnectionState:
        del settings
        return MT5ConnectionState(
            status=ConnectionStatus.CONNECTED,
            account_login=123456,
            server_name="Broker-Demo",
            account_name="Practice Demo",
            account_currency="USD",
            leverage=100,
            is_demo=True,
            trade_allowed=True,
            paper_trading_allowed=True,
            reason=None,
        )

    def submit_paper_order(self, settings: Settings, **kwargs) -> MT5OrderResult:
        del settings
        comment = str(kwargs.get("comment") or "rl_trade_paper")
        self._submitted_comments.append(comment)
        return MT5OrderResult(
            accepted=True,
            filled=False,
            broker_order_id="9001" if comment.startswith("signal:") else "9002",
            execution_price=None,
            execution_quantity=None,
            execution_time=datetime(2026, 4, 4, 13, 0, tzinfo=UTC),
            raw_result={"retcode": 10008, "comment": comment},
        )

    def list_order_history(
        self,
        settings: Settings,
        *,
        start_time: datetime,
        end_time: datetime | None = None,
    ) -> list[MT5HistoricalOrderRecord]:
        del settings, start_time, end_time
        if not any(comment.startswith("signal:") for comment in self._submitted_comments):
            return []
        return [
            MT5HistoricalOrderRecord(
                broker_order_id="9001",
                status="filled",
                execution_price=Decimal("1.1015"),
                execution_quantity=Decimal("0.25"),
                execution_time=datetime(2026, 4, 4, 13, 2, tzinfo=UTC),
                comment="signal:1",
                raw_record={"ticket": 9001},
            )
        ]

    def list_open_positions(self, settings: Settings) -> list[MT5PositionRecord]:
        del settings
        if not any(comment.startswith("signal:") for comment in self._submitted_comments):
            return []
        return [
            MT5PositionRecord(
                broker_order_id="9001",
                symbol_code="EURUSD",
                side="long",
                quantity=Decimal("0.25"),
                open_price=Decimal("1.1015"),
                current_price=Decimal("1.1030"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1100"),
                opened_at=datetime(2026, 4, 4, 13, 2, tzinfo=UTC),
                unrealized_pnl=Decimal("0.00038"),
                comment="signal:1",
                raw_record={"ticket": 9001},
            )
        ]


def run_dry_run(*, stdout: TextIO | None = None) -> CoreWorkflowDryRunSummary:
    output = stdout
    with TemporaryDirectory(prefix="rl-trade-core-workflow-") as temp_dir:
        workspace = Path(temp_dir)
        settings = Settings(_env_file=None, artifacts_root_dir=str(workspace / ".artifacts"))
        client = _build_client(database_path=workspace / "core_workflow.sqlite", settings=settings)

        with _patched_worker_runtime(session_factory=client.app.state.session_factory, settings=settings):
            validation = client.post("/api/v1/symbols/validate", json={"symbol": " eur/usd "})
            validation.raise_for_status()
            validation_body = validation.json()
            _write(output, f"validated symbol={validation_body['normalized_symbol']}")

            ingestion = client.post(
                "/api/v1/ingestion/request",
                json={
                    "symbol_code": "EURUSD",
                    "timeframes": ["1m", "5m", "15m"],
                    "sync_mode": "incremental",
                    "lookback_bars": 24,
                },
            )
            ingestion.raise_for_status()
            ingestion_job_id = ingestion.json()["job_id"]
            ingestion_status = client.get(f"/api/v1/jobs/ingestion/{ingestion_job_id}")
            ingestion_status.raise_for_status()
            ingestion_body = ingestion_status.json()
            with session_scope(client.app.state.session_factory) as session:
                ingestion_job = session.get(IngestionJob, ingestion_job_id)
                candles_written = int(ingestion_job.candles_written or 0) if ingestion_job is not None else 0
            _write(
                output,
                f"ingestion status={ingestion_body['status']} candles_written={candles_written}",
            )

            preprocessing = client.post(
                "/api/v1/preprocessing/request",
                json={
                    "symbol_code": "EURUSD",
                    "timeframes": ["1m", "5m", "15m"],
                    "primary_timeframe": "1m",
                    "feature_set_name": "baseline_forex",
                    "feature_set_version": "v1",
                    "indicator_window": 3,
                    "label_horizon_bars": 2,
                    "label_min_move_ratio": "0.0005",
                },
            )
            preprocessing.raise_for_status()
            preprocessing_job_id = preprocessing.json()["job_id"]
            preprocessing_status = client.get(f"/api/v1/jobs/preprocessing/{preprocessing_job_id}")
            preprocessing_status.raise_for_status()
            preprocessing_body = preprocessing_status.json()
            dataset_version_id = int(preprocessing_body["details"]["dataset_version_id"])
            _write(
                output,
                f"preprocessing status={preprocessing_body['status']} dataset_version_id={dataset_version_id}",
            )

            training = client.post(
                "/api/v1/training/supervised/request",
                json={
                    "dataset_version_id": dataset_version_id,
                    "algorithm": "auto_baseline",
                    "model_name": "baseline_classifier",
                    "validation_ratio": 0.25,
                    "walk_forward_folds": 2,
                },
            )
            training.raise_for_status()
            training_job_id = training.json()["supervised_training_job_id"]
            training_status = client.get(f"/api/v1/training/supervised/{training_job_id}")
            training_status.raise_for_status()
            training_body = training_status.json()
            model_id = int(training_body["model"]["model_id"])
            _write(output, f"training status={training_body['status']} model_id={model_id}")

            evaluation = client.post(
                "/api/v1/evaluations",
                json={
                    "model_type": "supervised",
                    "model_id": model_id,
                    "evaluation_type": "validation",
                    "confidence": 74.0,
                    "risk_to_reward": 2.4,
                    "sample_size": 140,
                    "max_drawdown": 12.0,
                    "metrics": {"source": "core_workflow_dry_run"},
                },
            )
            evaluation.raise_for_status()
            evaluation_body = evaluation.json()
            _write(output, f"evaluation approved={evaluation_body['decision']['approved']}")

            approved_symbols = client.get("/api/v1/evaluations/approved-symbols")
            approved_symbols.raise_for_status()
            approved_body = approved_symbols.json()
            _write(output, f"approved_symbols count={len(approved_body)}")

            started = client.post("/api/v1/trading/start")
            started.raise_for_status()
            started_body = started.json()
            _write(output, f"runtime enabled={started_body['enabled']}")

            signal = client.post(
                "/api/v1/trading/signals",
                json={
                    "symbol_code": "EURUSD",
                    "timeframe": "1m",
                    "side": "long",
                    "confidence": 74.0,
                    "entry_price": 1.1000,
                    "stop_loss": 1.0950,
                    "take_profit": 1.1100,
                    "model_type": "supervised",
                    "rationale": {"source": "core_workflow_dry_run"},
                },
            )
            signal.raise_for_status()
            signal_body = signal.json()
            _write(output, f"signal status={signal_body['status']} signal_id={signal_body['signal_id']}")

            order = client.post("/api/v1/trading/orders", json={"signal_id": signal_body["signal_id"], "quantity": 0.25})
            order.raise_for_status()
            order_body = order.json()
            _write(output, f"order status={order_body['status']} broker_order_id={order_body['broker_order_id']}")

            sync = client.post("/api/v1/trading/sync")
            sync.raise_for_status()
            sync_body = sync.json()
            _write(
                output,
                f"sync orders_updated={sync_body['orders_updated']} positions_updated={sync_body['positions_updated']}",
            )

            positions = client.get("/api/v1/trading/positions")
            positions.raise_for_status()
            positions_body = positions.json()["positions"]
            _write(output, f"positions count={len(positions_body)}")

            stopped = client.post("/api/v1/trading/stop")
            stopped.raise_for_status()
            stopped_body = stopped.json()
            _write(output, f"stop enabled={stopped_body['enabled']}")

        return CoreWorkflowDryRunSummary(
            symbol_code=str(validation_body["normalized_symbol"]),
            ingestion_status=str(ingestion_body["status"]),
            candles_written=candles_written,
            preprocessing_status=str(preprocessing_body["status"]),
            dataset_version_id=dataset_version_id,
            training_status=str(training_body["status"]),
            model_id=model_id,
            evaluation_approved=bool(evaluation_body["decision"]["approved"]),
            approved_symbol_count=len(approved_body),
            runtime_enabled=bool(started_body["enabled"]),
            signal_status=str(signal_body["status"]),
            order_status=str(order_body["status"]),
            sync_orders_updated=int(sync_body["orders_updated"]),
            sync_positions_updated=int(sync_body["positions_updated"]),
            open_position_count=len(positions_body),
            stopped=not bool(stopped_body["enabled"]),
        )


def run_cli() -> int:
    summary = run_dry_run(stdout=sys.stdout)
    print("Core workflow dry run completed.")
    print(
        "summary "
        f"symbol_code={summary.symbol_code} "
        f"ingestion_status={summary.ingestion_status} "
        f"preprocessing_status={summary.preprocessing_status} "
        f"training_status={summary.training_status} "
        f"evaluation_approved={summary.evaluation_approved} "
        f"signal_status={summary.signal_status} "
        f"order_status={summary.order_status} "
        f"open_position_count={summary.open_position_count} "
        f"stopped={summary.stopped}"
    )
    return 0


def _build_client(*, database_path: Path, settings: Settings) -> TestClient:
    database_url = f"sqlite+pysqlite:///{database_path}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    gateway = DryRunMT5Gateway()

    app = FastAPI(
        title="Forex Trainer & Paper Trading Dashboard API",
        version="0.1.0",
        summary="Core workflow dry-run API surface.",
    )
    app.state.settings = settings
    app.state.event_broadcaster = EventBroadcaster()
    app.state.session_factory = session_factory
    register_exception_handlers(app)
    app.include_router(api_router)

    app.dependency_overrides[get_api_settings] = lambda: settings
    app.dependency_overrides[require_authenticated_principal] = lambda: AuthPrincipal(
        subject="core-dry-run",
        roles=("operator",),
        auth_mode="disabled",
    )
    app.dependency_overrides[get_mt5_gateway] = lambda: gateway

    def override_db() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


@contextmanager
def _patched_worker_runtime(*, session_factory, settings: Settings) -> Iterator[None]:
    original_always_eager = celery_app.conf.task_always_eager
    original_eager_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    with ExitStack() as stack:
        stack.enter_context(patch("rl_trade_worker.tasks.get_session_factory", lambda: session_factory))
        stack.enter_context(patch("rl_trade_worker.task_base.get_session_factory", lambda: session_factory))
        stack.enter_context(patch("rl_trade_worker.tasks.get_settings", lambda: settings))
        stack.enter_context(patch("rl_trade_worker.tasks.MT5Gateway", DryRunMT5Gateway))
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
