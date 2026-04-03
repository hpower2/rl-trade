"""MT5 API endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_mt5_gateway
from rl_trade_api.app import create_app
from rl_trade_data.models.enums import ConnectionStatus
from rl_trade_trading import MT5ConnectionState, MT5IntegrationError, MT5SymbolRecord


class FakeMT5Gateway:
    def get_connection_state(self, settings):
        return MT5ConnectionState(
            status=ConnectionStatus.CONNECTED,
            account_login=123456,
            server_name="Broker-Demo",
            account_name="Trader Demo",
            account_currency="USD",
            leverage=100,
            is_demo=True,
            trade_allowed=True,
            paper_trading_allowed=True,
            reason=None,
            details={"terminal_connected": True},
        )

    def list_symbols(self, settings, query=None):
        if query == "FAIL":
            raise MT5IntegrationError("initialize_failed")
        return [
            MT5SymbolRecord(
                code="EURUSD",
                description="Euro vs Dollar",
                path="Forex\\Majors",
                visible=True,
                spread=12,
            )
        ]


def test_mt5_status_and_symbols_endpoints_are_registered() -> None:
    app = create_app()
    app.dependency_overrides[get_mt5_gateway] = lambda: FakeMT5Gateway()
    client = TestClient(app)

    status_response = client.get("/api/v1/mt5/status")
    symbols_response = client.get("/api/v1/mt5/symbols")

    assert status_response.status_code == 200
    assert status_response.json()["is_demo"] is True
    assert status_response.json()["paper_trading_allowed"] is True
    assert symbols_response.status_code == 200
    assert symbols_response.json()["count"] == 1
    assert symbols_response.json()["symbols"][0]["code"] == "EURUSD"

    openapi = app.openapi()
    assert "/api/v1/mt5/status" in openapi["paths"]
    assert "/api/v1/mt5/symbols" in openapi["paths"]


def test_mt5_symbols_endpoint_returns_503_when_gateway_is_unavailable() -> None:
    app = create_app()
    app.dependency_overrides[get_mt5_gateway] = lambda: FakeMT5Gateway()
    client = TestClient(app)

    response = client.get("/api/v1/mt5/symbols", params={"query": "FAIL"})

    assert response.status_code == 503
    assert response.json() == {
        "error": "http_error",
        "message": "MT5 symbol listing unavailable: initialize_failed.",
        "details": [],
    }
