"""Training service event emission tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_db_session, require_authenticated_principal
from rl_trade_api.api.routes.events import router as events_router
from rl_trade_api.api.v1.routes.training import router as training_router
from rl_trade_api.services import training as training_service
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings
from rl_trade_data import (
    Base,
    DatasetVersion,
    FeatureSet,
    JobStatus,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import DatasetStatus, Timeframe, TrainingType


def test_supervised_training_request_emits_live_training_progress_event(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'training_events_request.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        _, dataset_version_id = seed_ready_dataset(session, symbol_code="EURUSD")

    monkeypatch.setattr(training_service, "_enqueue_supervised_training_job", lambda *, job_id: None)
    client = build_test_client(session_factory)

    with client.websocket_connect("/ws/events?topics=training_progress") as websocket:
        response = client.post(
            "/api/v1/training/supervised/request",
            json={
                "dataset_version_id": dataset_version_id,
                "algorithm": "auto_baseline",
                "model_name": "baseline_classifier",
                "validation_ratio": 0.25,
                "walk_forward_folds": 2,
            },
        )
        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["delivery"] == "live"
    assert message["event"]["event_type"] == "training_progress"
    assert message["event"]["entity_type"] == "supervised_training_job"
    assert message["event"]["entity_id"] == "1"
    assert message["event"]["payload"] == {
        "job_id": 1,
        "training_request_id": 1,
        "dataset_version_id": dataset_version_id,
        "symbol_id": 1,
        "symbol_code": "EURUSD",
        "algorithm": "auto_baseline",
        "status": "pending",
        "progress_percent": 0,
        "source": "api_request",
    }
    engine.dispose()


def test_supervised_training_retry_emits_live_training_progress_event(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'training_events_retry.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        seed_failed_supervised_training_job(session, symbol_code="GBPUSD")

    monkeypatch.setattr(training_service, "_enqueue_supervised_training_job", lambda *, job_id: None)
    client = build_test_client(session_factory)

    with client.websocket_connect("/ws/events?topics=training_progress") as websocket:
        response = client.post("/api/v1/training/supervised/1/retry")
        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["delivery"] == "live"
    assert message["event"]["event_type"] == "training_progress"
    assert message["event"]["entity_id"] == "1"
    assert message["event"]["payload"]["status"] == "pending"
    assert message["event"]["payload"]["progress_percent"] == 0
    assert message["event"]["payload"]["source"] == "manual_retry"
    engine.dispose()


def build_test_client(session_factory) -> TestClient:
    app = FastAPI()
    app.include_router(events_router)
    app.include_router(training_router, prefix="/api/v1")
    app.state.settings = Settings(_env_file=None)
    app.state.event_broadcaster = EventBroadcaster()
    app.dependency_overrides[require_authenticated_principal] = lambda: AuthPrincipal(
        subject="test-operator",
        roles=("operator",),
        auth_mode="disabled",
    )

    def override_db_session() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def seed_ready_dataset(session, *, symbol_code: str) -> tuple[int, int]:
    symbol = Symbol(code=symbol_code, base_currency=symbol_code[:3], quote_currency=symbol_code[3:], provider="mt5")
    session.add(symbol)
    session.flush()
    feature_set = FeatureSet(name="baseline_forex", version="v1", feature_columns=["close"])
    session.add(feature_set)
    session.flush()
    dataset_version = DatasetVersion(
        symbol_id=symbol.id,
        feature_set_id=feature_set.id,
        status=DatasetStatus.READY,
        version_tag=f"{symbol_code.lower()}-dataset",
        primary_timeframe=Timeframe.M1,
        included_timeframes=["1m", "5m", "15m"],
        label_name="trade_setup_direction",
        row_count=12,
        data_hash=f"{symbol_code.lower()}-hash",
    )
    session.add(dataset_version)
    session.flush()
    return symbol.id, dataset_version.id


def seed_failed_supervised_training_job(session, *, symbol_code: str) -> None:
    symbol_id, dataset_version_id = seed_ready_dataset(session, symbol_code=symbol_code)
    training_request = TrainingRequest(
        symbol_id=symbol_id,
        dataset_version_id=dataset_version_id,
        training_type=TrainingType.SUPERVISED,
        status=JobStatus.FAILED,
        requested_timeframes=["1m", "5m", "15m"],
    )
    session.add(training_request)
    session.flush()
    session.add(
        SupervisedTrainingJob(
            training_request_id=training_request.id,
            dataset_version_id=dataset_version_id,
            algorithm="nearest_centroid",
            status=JobStatus.FAILED,
            progress_percent=75,
            metrics={"validation_accuracy": 0.25},
            error_message="sample failure",
        )
    )
