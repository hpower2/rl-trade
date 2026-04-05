"""CORS middleware regression tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from rl_trade_api.app import create_app


def test_auth_session_get_echoes_allowed_private_network_origin() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/v1/auth/session",
        headers={"Origin": "http://10.0.10.8:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://10.0.10.8:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["vary"] == "Origin"


def test_auth_session_preflight_allows_private_network_requests() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/auth/session",
        headers={
            "Origin": "http://10.0.10.8:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
            "Access-Control-Request-Private-Network": "true",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://10.0.10.8:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-private-network"] == "true"
    assert response.headers["vary"] == "Origin"


def test_auth_session_preflight_rejects_untrusted_public_origin() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/auth/session",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert response.text == "Disallowed CORS origin"
