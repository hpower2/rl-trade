"""Symbol validation API endpoint tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import select

from rl_trade_api.api.deps import get_db_session, get_mt5_gateway
from rl_trade_api.app import create_app
from rl_trade_data import Base, Symbol, SymbolValidationResult, build_engine, build_session_factory, session_scope
from rl_trade_trading import MT5IntegrationError, SymbolValidationDecision


class FakeSymbolValidationGateway:
    def validate_symbol(self, settings, requested_symbol: str) -> SymbolValidationDecision:
        normalized_input = requested_symbol.strip().upper().replace("/", "")
        if normalized_input == "EURUSD":
            return SymbolValidationDecision(
                requested_symbol=requested_symbol,
                normalized_input="EURUSD",
                normalized_symbol="EURUSD",
                provider="mt5",
                is_valid=True,
                base_currency="EUR",
                quote_currency="USD",
                details={"matched_by": "exact"},
            )
        if normalized_input == "BAD$":
            return SymbolValidationDecision(
                requested_symbol=requested_symbol,
                normalized_input="BAD$",
                normalized_symbol=None,
                provider="mt5",
                is_valid=False,
                reason="invalid_format",
                details={"normalized_input": "BAD$"},
            )
        raise MT5IntegrationError("initialize_failed")


def test_validate_symbol_endpoint_persists_valid_symbol_and_result(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'symbol_validation.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_mt5_gateway] = lambda: FakeSymbolValidationGateway()
    client = TestClient(app)

    response = client.post("/api/v1/symbols/validate", json={"symbol": " eur/usd "})

    assert response.status_code == 200
    assert response.json()["is_valid"] is True
    assert response.json()["normalized_input"] == "EURUSD"
    assert response.json()["normalized_symbol"] == "EURUSD"
    assert response.json()["symbol_id"] is not None

    with session_scope(session_factory) as session:
        stored_symbol = session.scalar(select(Symbol).where(Symbol.code == "EURUSD"))
        stored_result = session.scalar(
            select(SymbolValidationResult).where(SymbolValidationResult.requested_symbol == "eur/usd")
        )

    assert stored_symbol is not None
    assert stored_symbol.base_currency == "EUR"
    assert stored_result is not None
    assert stored_result.is_valid is True
    assert stored_result.symbol_id == stored_symbol.id
    engine.dispose()


def test_validate_symbol_endpoint_returns_invalid_result_for_bad_symbol(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'symbol_validation_invalid.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_mt5_gateway] = lambda: FakeSymbolValidationGateway()
    client = TestClient(app)

    response = client.post("/api/v1/symbols/validate", json={"symbol": "BAD$"})

    assert response.status_code == 200
    assert response.json()["is_valid"] is False
    assert response.json()["reason"] == "invalid_format"
    assert response.json()["symbol_id"] is None

    with session_scope(session_factory) as session:
        stored_result = session.scalar(
            select(SymbolValidationResult).where(SymbolValidationResult.requested_symbol == "BAD$")
        )

    assert stored_result is not None
    assert stored_result.is_valid is False
    engine.dispose()


def test_validate_symbol_endpoint_returns_503_when_mt5_is_unavailable(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'symbol_validation_unavailable.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_mt5_gateway] = lambda: FakeSymbolValidationGateway()
    client = TestClient(app)

    response = client.post("/api/v1/symbols/validate", json={"symbol": "AUDCAD"})

    assert response.status_code == 503
    assert response.json() == {
        "error": "http_error",
        "message": "MT5 symbol validation unavailable: initialize_failed.",
        "details": [],
    }

    with session_scope(session_factory) as session:
        stored_count = session.execute(select(SymbolValidationResult)).scalars().all()

    assert stored_count == []
    engine.dispose()
