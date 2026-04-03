"""API job polling endpoint tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_db_session
from rl_trade_api.app import create_app
from rl_trade_data import Base, IngestionJob, JobStatus, Symbol, build_engine, build_session_factory, session_scope


def test_job_status_endpoint_reads_db_backed_job_state(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_jobs.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURJPY", base_currency="EUR", quote_currency="JPY")
        session.add(symbol)
        session.flush()
        job = IngestionJob(
            symbol_id=symbol.id,
            status=JobStatus.RUNNING,
            progress_percent=45,
            requested_timeframes=["1m", "5m"],
            details={"phase": "fetching"},
        )
        session.add(job)
        session.flush()
        job_id = job.id

    app = create_app()

    def override_db_session() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.get(f"/api/v1/jobs/ingestion/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_type"] == "ingestion"
    assert response.json()["queue_name"] == "ingestion"
    assert response.json()["status"] == "running"
    assert response.json()["progress_percent"] == 45
    assert response.json()["details"]["phase"] == "fetching"
    assert "/api/v1/jobs/{job_type}/{job_id}" in app.openapi()["paths"]
    engine.dispose()


def test_job_status_endpoint_returns_404_for_unknown_job(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_jobs_missing.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    app = create_app()

    def override_db_session() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.get("/api/v1/jobs/ingestion/999")

    assert response.status_code == 404
    assert response.json() == {
        "error": "http_error",
        "message": "ingestion job 999 was not found.",
        "details": [],
    }
    engine.dispose()
