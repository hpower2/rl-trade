"""Manual dry-run smoke path for the paper-trading workflow."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import TextIO

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_api_settings, get_db_session, get_mt5_gateway, require_authenticated_principal
from rl_trade_api.api.v1.routes.trading import router as trading_router
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings
from rl_trade_data import ApprovedModel, Base, Symbol, build_engine, build_session_factory, session_scope
from rl_trade_data.models import ConnectionStatus, ModelType
from rl_trade_trading import MT5ConnectionState, MT5HistoricalOrderRecord, MT5OrderResult, MT5PositionRecord


@dataclass(frozen=True, slots=True)
class DryRunSummary:
    started: bool
    signal_status: str
    opening_order_status: str
    first_sync_orders_updated: int
    first_sync_positions_updated: int
    open_position_count_after_sync: int
    closing_order_status: str
    second_sync_positions_updated: int
    final_position_status: str
    stopped: bool


class DryRunMT5Gateway:
    def __init__(self) -> None:
        self._submitted_comments: list[str] = []

    def get_connection_state(self, settings: Settings) -> MT5ConnectionState:
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
        comment = str(kwargs.get("comment") or "rl_trade_paper")
        self._submitted_comments.append(comment)
        broker_order_id = "9001" if comment.startswith("signal:") else "9002"
        return MT5OrderResult(
            accepted=True,
            filled=False,
            broker_order_id=broker_order_id,
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
        records: list[MT5HistoricalOrderRecord] = []
        if any(comment.startswith("signal:") for comment in self._submitted_comments):
            records.append(
                MT5HistoricalOrderRecord(
                    broker_order_id="9001",
                    status="filled",
                    execution_price=Decimal("1.1015"),
                    execution_quantity=Decimal("0.25"),
                    execution_time=datetime(2026, 4, 4, 13, 2, tzinfo=UTC),
                    comment="signal:1",
                    raw_record={"ticket": 9001},
                )
            )
        if any(comment.startswith("close_position:") for comment in self._submitted_comments):
            records.append(
                MT5HistoricalOrderRecord(
                    broker_order_id="9002",
                    status="filled",
                    execution_price=Decimal("1.1080"),
                    execution_quantity=Decimal("0.25"),
                    execution_time=datetime(2026, 4, 4, 14, 0, tzinfo=UTC),
                    comment="close_position:1",
                    raw_record={"ticket": 9002},
                )
            )
        return records

    def list_open_positions(self, settings: Settings) -> list[MT5PositionRecord]:
        if any(comment.startswith("close_position:") for comment in self._submitted_comments):
            return []
        if any(comment.startswith("signal:") for comment in self._submitted_comments):
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
        return []


def run_dry_run(*, stdout: TextIO | None = None) -> DryRunSummary:
    output = stdout
    with TemporaryDirectory(prefix="rl-trade-paper-dry-run-") as temp_dir:
        client = _build_client(Path(temp_dir) / "paper_trading_dry_run.sqlite")

        started = client.post("/api/v1/trading/start").json()
        _write(output, f"start enabled={started['enabled']} account={started['account_login']}")

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
                "rationale": {"source": "paper_trading_dry_run"},
            },
        ).json()
        _write(output, f"signal status={signal['status']} symbol={signal['symbol_code']}")

        opening_order = client.post("/api/v1/trading/orders", json={"signal_id": signal["signal_id"], "quantity": 0.25}).json()
        _write(output, f"opening_order status={opening_order['status']} broker_order_id={opening_order['broker_order_id']}")

        first_sync = client.post("/api/v1/trading/sync").json()
        _write(
            output,
            "first_sync "
            f"orders_updated={first_sync['orders_updated']} "
            f"positions_updated={first_sync['positions_updated']}",
        )

        positions_after_first_sync = client.get("/api/v1/trading/positions").json()["positions"]
        open_position = positions_after_first_sync[0]
        _write(output, f"open_position status={open_position['status']} position_id={open_position['position_id']}")

        close_response = client.post(f"/api/v1/trading/positions/{open_position['position_id']}/close").json()
        closing_order = close_response["closing_order"]
        _write(output, f"closing_order status={closing_order['status']} broker_order_id={closing_order['broker_order_id']}")

        second_sync = client.post("/api/v1/trading/sync").json()
        _write(output, f"second_sync positions_updated={second_sync['positions_updated']}")

        final_positions = client.get("/api/v1/trading/positions").json()["positions"]
        final_position = final_positions[0]
        _write(output, f"final_position status={final_position['status']} realized_pnl={final_position['realized_pnl']}")

        stopped = client.post("/api/v1/trading/stop").json()
        _write(output, f"stop enabled={stopped['enabled']}")

        return DryRunSummary(
            started=bool(started["enabled"]),
            signal_status=str(signal["status"]),
            opening_order_status=str(opening_order["status"]),
            first_sync_orders_updated=int(first_sync["orders_updated"]),
            first_sync_positions_updated=int(first_sync["positions_updated"]),
            open_position_count_after_sync=len(positions_after_first_sync),
            closing_order_status=str(closing_order["status"]),
            second_sync_positions_updated=int(second_sync["positions_updated"]),
            final_position_status=str(final_position["status"]),
            stopped=not bool(stopped["enabled"]),
        )


def run_cli() -> int:
    summary = run_dry_run(stdout=sys.stdout)
    print("Paper-trading dry run completed.")
    print(
        "summary "
        f"started={summary.started} "
        f"signal_status={summary.signal_status} "
        f"opening_order_status={summary.opening_order_status} "
        f"final_position_status={summary.final_position_status} "
        f"stopped={summary.stopped}"
    )
    return 0


def _build_client(database_path: Path) -> TestClient:
    database_url = f"sqlite+pysqlite:///{database_path}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        _seed_approved_symbol(session)

    gateway = DryRunMT5Gateway()
    app = FastAPI()
    app.include_router(trading_router, prefix="/api/v1")
    app.state.event_broadcaster = EventBroadcaster()
    app.dependency_overrides[get_api_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[require_authenticated_principal] = lambda: AuthPrincipal(
        subject="paper-dry-run",
        roles=("operator",),
        auth_mode="disabled",
    )
    app.dependency_overrides[get_mt5_gateway] = lambda: gateway

    def override_db() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def _seed_approved_symbol(session) -> None:
    symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
    session.add(symbol)
    session.flush()
    session.add(
        ApprovedModel(
            symbol_id=symbol.id,
            supervised_model_id=symbol.id,
            model_type=ModelType.SUPERVISED.value,
            confidence=Decimal("75.0"),
            risk_to_reward=Decimal("2.5"),
            is_active=True,
        )
    )


def _write(stdout: TextIO | None, message: str) -> None:
    if stdout is not None:
        stdout.write(f"{message}\n")


if __name__ == "__main__":
    raise SystemExit(run_cli())
