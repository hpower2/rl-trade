"""API health and status endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from rl_trade_api.app import create_app
from rl_trade_api.schemas.system import ComponentHealthResponse
from rl_trade_api.services import health as health_service


def test_health_endpoints_and_openapi_are_registered() -> None:
    app = create_app()
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200

    openapi = app.openapi()
    assert "/health" in openapi["paths"]
    assert "/health/db" in openapi["paths"]
    assert "/health/redis" in openapi["paths"]
    assert "/health/gpu" in openapi["paths"]
    assert "/api/v1/system/status" in openapi["paths"]


def test_component_health_routes_return_503_for_unavailable_services(monkeypatch) -> None:
    client = TestClient(create_app())

    monkeypatch.setattr(
        health_service,
        "check_database_health",
        lambda engine: ComponentHealthResponse(name="db", status="unavailable", details={"reason": "db_down"}),
    )
    monkeypatch.setattr(
        health_service,
        "check_redis_health",
        lambda client: ComponentHealthResponse(name="redis", status="unavailable", details={"reason": "redis_down"}),
    )
    monkeypatch.setattr(
        health_service,
        "check_gpu_health",
        lambda: ComponentHealthResponse(name="gpu", status="unavailable", details={"reason": "gpu_down"}),
    )

    db_response = client.get("/health/db")
    redis_response = client.get("/health/redis")
    gpu_response = client.get("/health/gpu")

    assert db_response.status_code == 503
    assert redis_response.status_code == 503
    assert gpu_response.status_code == 503
    assert db_response.json()["details"]["reason"] == "db_down"
    assert redis_response.json()["details"]["reason"] == "redis_down"
    assert gpu_response.json()["details"]["reason"] == "gpu_down"


def test_system_status_summary_reports_degraded_components(monkeypatch) -> None:
    client = TestClient(create_app())

    monkeypatch.setattr(
        health_service,
        "check_database_health",
        lambda engine: ComponentHealthResponse(name="db", status="ok", details={"dialect": "sqlite"}),
    )
    monkeypatch.setattr(
        health_service,
        "check_redis_health",
        lambda client: ComponentHealthResponse(name="redis", status="unavailable", details={"reason": "redis_down"}),
    )
    monkeypatch.setattr(
        health_service,
        "check_gpu_health",
        lambda: ComponentHealthResponse(name="gpu", status="unavailable", details={"reason": "gpu_down"}),
    )

    response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["paper_trading_only"] is True
    assert response.json()["components"]["api"]["status"] == "ok"
    assert response.json()["components"]["db"]["status"] == "ok"
    assert response.json()["components"]["redis"]["status"] == "unavailable"
    assert response.json()["components"]["gpu"]["status"] == "unavailable"
