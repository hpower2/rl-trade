"""Evaluation event emission tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_api_settings, get_db_session, require_authenticated_principal
from rl_trade_api.api.routes.events import router as events_router
from rl_trade_api.api.v1.routes.evaluations import router as evaluations_router
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_api.services.events import EventBroadcaster
from rl_trade_common.settings import Settings
from rl_trade_data import Base, DatasetVersion, FeatureSet, JobStatus, SupervisedModel, SupervisedTrainingJob, Symbol, TrainingRequest, build_engine, build_session_factory, session_scope
from rl_trade_data.models import DatasetStatus, Timeframe, TrainingType


def test_approved_evaluation_emits_evaluation_and_approval_events(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'evaluation_events_approved.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        model_id = seed_supervised_model_fixture(session, code="EURUSD")

    client = build_test_client(session_factory)

    with client.websocket_connect("/ws/events?topics=evaluation_status,approval_status") as websocket:
        response = client.post(
            "/api/v1/evaluations",
            json={
                "model_type": "supervised",
                "model_id": model_id,
                "evaluation_type": "validation",
                "confidence": 74.0,
                "risk_to_reward": 2.4,
                "sample_size": 140,
                "max_drawdown": 12.0,
            },
        )
        evaluation_message = websocket.receive_json()
        approval_message = websocket.receive_json()

    assert response.status_code == 200
    assert evaluation_message["event"]["event_type"] == "evaluation_status"
    assert evaluation_message["event"]["payload"]["approved"] is True
    assert evaluation_message["event"]["payload"]["model_status"] == "approved"
    assert evaluation_message["event"]["payload"]["symbol_code"] == "EURUSD"
    assert approval_message["event"]["event_type"] == "approval_status"
    assert approval_message["event"]["payload"]["approved"] is True
    assert approval_message["event"]["payload"]["is_active_approval"] is True
    assert approval_message["event"]["payload"]["approved_model_id"] == 1
    engine.dispose()


def test_rejected_evaluation_emits_blocked_approval_event(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'evaluation_events_rejected.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        model_id = seed_supervised_model_fixture(session, code="GBPUSD")

    client = build_test_client(session_factory)

    with client.websocket_connect("/ws/events?topics=evaluation_status,approval_status") as websocket:
        response = client.post(
            "/api/v1/evaluations",
            json={
                "model_type": "supervised",
                "model_id": model_id,
                "evaluation_type": "backtest",
                "confidence": 63.0,
                "risk_to_reward": 1.9,
                "sample_size": 60,
                "max_drawdown": 24.0,
                "has_critical_data_issue": True,
            },
        )
        evaluation_message = websocket.receive_json()
        approval_message = websocket.receive_json()

    assert response.status_code == 200
    assert evaluation_message["event"]["event_type"] == "evaluation_status"
    assert evaluation_message["event"]["payload"]["approved"] is False
    assert "confidence_below_threshold" in evaluation_message["event"]["payload"]["decision_reasons"]
    assert approval_message["event"]["event_type"] == "approval_status"
    assert approval_message["event"]["payload"]["approved"] is False
    assert approval_message["event"]["payload"]["is_active_approval"] is False
    assert approval_message["event"]["payload"]["approved_model_id"] is None
    assert approval_message["event"]["payload"]["model_status"] == "rejected"
    engine.dispose()


def build_test_client(session_factory) -> TestClient:
    app = FastAPI()
    app.include_router(events_router)
    app.include_router(evaluations_router, prefix="/api/v1")
    app.state.settings = Settings(_env_file=None)
    app.state.event_broadcaster = EventBroadcaster()
    app.dependency_overrides[get_api_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[require_authenticated_principal] = lambda: AuthPrincipal(
        subject="test-operator",
        roles=("operator",),
        auth_mode="disabled",
    )

    def override_db() -> Iterator[object]:
        with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def seed_supervised_model_fixture(session, *, code: str) -> int:
    symbol = Symbol(code=code, base_currency=code[:3], quote_currency=code[3:], provider="mt5")
    session.add(symbol)
    session.flush()
    feature_set = FeatureSet(name="baseline_forex", version=f"{code.lower()}-v1", feature_columns=["close"])
    session.add(feature_set)
    session.flush()
    dataset_version = DatasetVersion(
        symbol_id=symbol.id,
        feature_set_id=feature_set.id,
        status=DatasetStatus.READY,
        version_tag=f"{code.lower()}-dataset-v1",
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
        status=JobStatus.SUCCEEDED,
        requested_timeframes=["1m", "5m", "15m"],
    )
    session.add(training_request)
    session.flush()
    training_job = SupervisedTrainingJob(
        training_request_id=training_request.id,
        dataset_version_id=dataset_version.id,
        status=JobStatus.SUCCEEDED,
        algorithm="nearest_centroid",
        metrics={"validation_accuracy": 0.76},
    )
    session.add(training_job)
    session.flush()
    model = SupervisedModel(
        training_job_id=training_job.id,
        symbol_id=symbol.id,
        dataset_version_id=dataset_version.id,
        feature_set_id=feature_set.id,
        status="trained",
        model_name="baseline_classifier",
        version_tag=f"{code.lower()}-model-v1",
        algorithm="nearest_centroid",
        storage_uri=f".artifacts/{code.lower()}/v1/model.json",
    )
    session.add(model)
    session.flush()
    return model.id
