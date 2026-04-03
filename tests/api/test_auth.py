"""Authentication and session endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from rl_trade_common.settings import Settings
from rl_trade_api.api.deps import get_api_settings
from rl_trade_api.app import create_app


def test_session_endpoint_returns_local_operator_when_auth_is_disabled() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "auth_mode": "disabled",
        "subject": "operator",
        "roles": ["operator"],
    }

    openapi = app.openapi()
    assert "/api/v1/auth/session" in openapi["paths"]
    assert any(
        scheme.get("type") == "http" and scheme.get("scheme") == "bearer"
        for scheme in openapi["components"]["securitySchemes"].values()
    )


def test_session_endpoint_requires_bearer_token_when_static_token_auth_is_enabled() -> None:
    app = create_app()
    app.dependency_overrides[get_api_settings] = lambda: Settings(
        _env_file=None,
        api_auth_mode="static_token",
        api_auth_token="topsecret",
    )
    client = TestClient(app)

    response = client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": "http_error",
        "message": "Authentication required.",
        "details": [],
    }


def test_session_endpoint_accepts_valid_bearer_token() -> None:
    app = create_app()
    app.dependency_overrides[get_api_settings] = lambda: Settings(
        _env_file=None,
        api_auth_mode="static_token",
        api_auth_token="topsecret",
        api_auth_subject="api-operator",
    )
    client = TestClient(app)

    response = client.get(
        "/api/v1/auth/session",
        headers={"Authorization": "Bearer topsecret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "auth_mode": "static_token",
        "subject": "api-operator",
        "roles": ["operator"],
    }
