"""API job polling endpoint tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_db_session
from rl_trade_api.app import create_app
from rl_trade_data import (
    Base,
    DatasetVersion,
    FeatureSet,
    IngestionJob,
    JobStatus,
    RLTrainingJob,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import DatasetStatus, Timeframe, TrainingType


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


def test_job_status_endpoint_exposes_supervised_training_metrics(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_supervised_jobs.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="USDJPY", base_currency="USD", quote_currency="JPY")
        session.add(symbol)
        session.flush()
        feature_set = FeatureSet(name="baseline_forex", version="v1", feature_columns=["close"])
        session.add(feature_set)
        session.flush()
        dataset_version = DatasetVersion(
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            status=DatasetStatus.READY,
            version_tag="trade_setup-demo",
            primary_timeframe=Timeframe.M1,
            included_timeframes=["1m", "5m", "15m"],
            label_name="trade_setup_direction",
        )
        session.add(dataset_version)
        session.flush()
        training_request = TrainingRequest(
            symbol_id=symbol.id,
            dataset_version_id=dataset_version.id,
            training_type=TrainingType.SUPERVISED,
            status=JobStatus.RUNNING,
            requested_timeframes=["1m", "5m", "15m"],
        )
        session.add(training_request)
        session.flush()
        job = SupervisedTrainingJob(
            training_request_id=training_request.id,
            dataset_version_id=dataset_version.id,
            status=JobStatus.SUCCEEDED,
            algorithm="nearest_centroid",
            progress_percent=100,
            metrics={"validation_accuracy": 0.75, "device": "cpu"},
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

    response = client.get(f"/api/v1/jobs/supervised_training/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_type"] == "supervised_training"
    assert response.json()["queue_name"] == "supervised_training"
    assert response.json()["details"]["algorithm"] == "nearest_centroid"
    assert response.json()["details"]["dataset_version_id"] == dataset_version.id
    assert response.json()["details"]["metrics"]["device"] == "cpu"
    engine.dispose()


def test_job_status_endpoint_exposes_rl_training_metrics(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_rl_jobs.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="GBPJPY", base_currency="GBP", quote_currency="JPY")
        session.add(symbol)
        session.flush()
        feature_set = FeatureSet(name="baseline_forex", version="v1", feature_columns=["close"])
        session.add(feature_set)
        session.flush()
        dataset_version = DatasetVersion(
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            status=DatasetStatus.READY,
            version_tag="trade_setup-rl-demo",
            primary_timeframe=Timeframe.M1,
            included_timeframes=["1m", "5m", "15m"],
            label_name="trade_setup_direction",
        )
        session.add(dataset_version)
        session.flush()
        training_request = TrainingRequest(
            symbol_id=symbol.id,
            dataset_version_id=dataset_version.id,
            training_type=TrainingType.RL,
            status=JobStatus.RUNNING,
            requested_timeframes=["1m", "5m", "15m"],
        )
        session.add(training_request)
        session.flush()
        job = RLTrainingJob(
            training_request_id=training_request.id,
            dataset_version_id=dataset_version.id,
            status=JobStatus.SUCCEEDED,
            algorithm="ppo",
            environment_name="ForexTradingEnv",
            progress_percent=100,
            metrics={"total_reward": 1.25, "device": "cpu"},
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

    response = client.get(f"/api/v1/jobs/rl_training/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_type"] == "rl_training"
    assert response.json()["queue_name"] == "rl_training"
    assert response.json()["details"]["algorithm"] == "ppo"
    assert response.json()["details"]["dataset_version_id"] == dataset_version.id
    assert response.json()["details"]["metrics"]["device"] == "cpu"
    engine.dispose()
