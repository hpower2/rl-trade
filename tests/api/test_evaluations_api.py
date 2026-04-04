"""Evaluation and approval API tests."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rl_trade_api.api.deps import get_api_settings, get_db_session
from rl_trade_api.api.deps import require_authenticated_principal
from rl_trade_api.api.v1.routes.evaluations import router as evaluations_router
from rl_trade_api.services.auth import AuthPrincipal
from rl_trade_common.settings import Settings
from rl_trade_data import (
    ApprovedModel,
    AuditLog,
    Base,
    DatasetVersion,
    FeatureSet,
    ModelEvaluation,
    RLModel,
    RLTrainingJob,
    SupervisedModel,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import (
    AuditOutcome,
    DatasetStatus,
    EvaluationType,
    JobStatus,
    ModelStatus,
    ModelType,
    Timeframe,
    TrainingType,
)
from rl_trade_trading import is_symbol_tradeable


def test_create_model_evaluation_persists_report_and_approval(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_evaluations.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        model_id, symbol_id = seed_supervised_model_fixture(session)

    client = build_test_client(session_factory)

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
            "metrics": {"win_rate": 0.58},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["approved"] is True
    assert body["approved_model_id"] is not None
    assert body["model_status"] == "approved"

    with session_scope(session_factory) as session:
        evaluations = session.query(ModelEvaluation).all()
        approvals = session.query(ApprovedModel).all()
        model = session.get(SupervisedModel, model_id)
        audit_logs = session.query(AuditLog).all()
        tradeable = is_symbol_tradeable(session, symbol_id=symbol_id)

    assert len(evaluations) == 1
    assert evaluations[0].metrics["sample_size"] == 140
    assert len(approvals) == 1
    assert approvals[0].is_active is True
    assert model is not None
    assert model.status is ModelStatus.APPROVED
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.SUCCESS
    assert tradeable is True
    engine.dispose()


def test_create_model_evaluation_rejects_low_confidence_and_high_drawdown(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_evaluations_reject.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        model_id, symbol_id = seed_supervised_model_fixture(session)

    client = build_test_client(session_factory)

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

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["approved"] is False
    assert body["approved_model_id"] is None
    assert body["model_status"] == "rejected"
    assert "confidence_below_threshold" in body["decision"]["reasons"]
    assert "drawdown_above_threshold" in body["decision"]["reasons"]

    with session_scope(session_factory) as session:
        approvals = session.query(ApprovedModel).all()
        model = session.get(SupervisedModel, model_id)
        audit_logs = session.query(AuditLog).all()
        tradeable = is_symbol_tradeable(session, symbol_id=symbol_id)

    assert approvals == []
    assert model is not None
    assert model.status is ModelStatus.REJECTED
    assert len(audit_logs) == 1
    assert audit_logs[0].outcome is AuditOutcome.BLOCKED
    assert tradeable is False
    engine.dispose()


def test_approved_symbol_query_returns_active_models(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_approved_symbols.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        active_model_id, active_symbol_id = seed_supervised_model_fixture(session, code="USDCHF")
        inactive_model_id, inactive_symbol_id = seed_supervised_model_fixture(session, code="EURCHF")

        session.add(
            ApprovedModel(
                symbol_id=active_symbol_id,
                supervised_model_id=active_model_id,
                model_type=ModelType.SUPERVISED.value,
                confidence=Decimal("74.0"),
                risk_to_reward=Decimal("2.4"),
                is_active=True,
            )
        )
        session.add(
            ApprovedModel(
                symbol_id=inactive_symbol_id,
                supervised_model_id=inactive_model_id,
                model_type=ModelType.SUPERVISED.value,
                confidence=Decimal("72.0"),
                risk_to_reward=Decimal("2.2"),
                is_active=False,
            )
        )

    client = build_test_client(session_factory)

    response = client.get("/api/v1/evaluations/approved-symbols")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["symbol_code"] == "USDCHF"
    assert body[0]["model_type"] == "supervised"
    engine.dispose()


def test_model_registry_query_lists_models_with_active_approval_state(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_model_registry.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        supervised_model_id, supervised_symbol_id = seed_supervised_model_fixture(session, code="USDJPY")
        rl_model_id, rl_symbol_id = seed_rl_model_fixture(session, code="EURJPY")
        session.add(
            ApprovedModel(
                symbol_id=supervised_symbol_id,
                supervised_model_id=supervised_model_id,
                model_type=ModelType.SUPERVISED.value,
                confidence=Decimal("76.0"),
                risk_to_reward=Decimal("2.5"),
                is_active=True,
            )
        )

    client = build_test_client(session_factory)

    response = client.get("/api/v1/evaluations/models")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2

    by_symbol = {item["symbol_code"]: item for item in body}
    assert by_symbol["USDJPY"]["model_type"] == "supervised"
    assert by_symbol["USDJPY"]["model_id"] == supervised_model_id
    assert by_symbol["USDJPY"]["is_active_approval"] is True
    assert by_symbol["USDJPY"]["approved_model_id"] is not None
    assert by_symbol["EURJPY"]["model_type"] == "rl"
    assert by_symbol["EURJPY"]["model_id"] == rl_model_id
    assert by_symbol["EURJPY"]["is_active_approval"] is False
    assert by_symbol["EURJPY"]["approved_model_id"] is None
    engine.dispose()


def test_evaluation_report_query_lists_persisted_reports_with_filters(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_evaluation_reports.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        supervised_model_id, _ = seed_supervised_model_fixture(session, code="GBPUSD")
        other_model_id, _ = seed_supervised_model_fixture(session, code="AUDUSD")

        session.add(
            ModelEvaluation(
                supervised_model_id=supervised_model_id,
                evaluation_type=EvaluationType.VALIDATION,
                dataset_version_id=None,
                confidence=Decimal("73.0"),
                risk_to_reward=Decimal("2.3"),
                max_drawdown=Decimal("11.0"),
                metrics={
                    "sample_size": 125,
                    "decision_reasons": [],
                },
            )
        )
        session.add(
            ModelEvaluation(
                supervised_model_id=other_model_id,
                evaluation_type=EvaluationType.BACKTEST,
                dataset_version_id=None,
                confidence=Decimal("62.0"),
                risk_to_reward=Decimal("1.8"),
                max_drawdown=Decimal("24.0"),
                metrics={
                    "sample_size": 48,
                    "decision_reasons": ["confidence_below_threshold", "drawdown_above_threshold"],
                },
            )
        )

    client = build_test_client(session_factory)

    response = client.get("/api/v1/evaluations/reports", params={"symbol_code": "GBPUSD", "model_type": "supervised"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["symbol_code"] == "GBPUSD"
    assert body[0]["model_type"] == "supervised"
    assert body[0]["sample_size"] == 125
    assert body[0]["approved"] is False
    assert body[0]["decision_reasons"] == []
    engine.dispose()


def test_approving_new_model_version_deactivates_previous_active_approval(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_approval_lifecycle.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        first_model_id, symbol_id = seed_supervised_model_fixture(session, code="EURUSD", version_suffix="v1")
        second_model_id, _ = seed_supervised_model_fixture(session, code="EURUSD", version_suffix="v2")

    client = build_test_client(session_factory)

    first_response = client.post(
        "/api/v1/evaluations",
        json={
            "model_type": "supervised",
            "model_id": first_model_id,
            "evaluation_type": "validation",
            "confidence": 74.0,
            "risk_to_reward": 2.3,
            "sample_size": 140,
            "max_drawdown": 10.0,
        },
    )
    second_response = client.post(
        "/api/v1/evaluations",
        json={
            "model_type": "supervised",
            "model_id": second_model_id,
            "evaluation_type": "validation",
            "confidence": 78.0,
            "risk_to_reward": 2.7,
            "sample_size": 155,
            "max_drawdown": 9.0,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    with session_scope(session_factory) as session:
        approvals = session.query(ApprovedModel).order_by(ApprovedModel.id.asc()).all()
        tradeable = is_symbol_tradeable(session, symbol_id=symbol_id)

    assert len(approvals) == 2
    assert approvals[0].supervised_model_id == first_model_id
    assert approvals[0].is_active is False
    assert approvals[0].revoked_at is not None
    assert approvals[1].supervised_model_id == second_model_id
    assert approvals[1].is_active is True
    assert approvals[1].revoked_at is None
    assert tradeable is True

    approved_symbols_response = client.get("/api/v1/evaluations/approved-symbols", params={"symbol_code": "EURUSD"})
    models_response = client.get("/api/v1/evaluations/models", params={"symbol_code": "EURUSD"})

    assert approved_symbols_response.status_code == 200
    assert len(approved_symbols_response.json()) == 1
    assert approved_symbols_response.json()[0]["model_id"] == second_model_id

    assert models_response.status_code == 200
    by_model_id = {item["model_id"]: item for item in models_response.json()}
    assert by_model_id[first_model_id]["is_active_approval"] is False
    assert by_model_id[second_model_id]["is_active_approval"] is True
    engine.dispose()


def test_rejecting_active_model_revokes_tradeable_state(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'api_rejection_lifecycle.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        model_id, symbol_id = seed_supervised_model_fixture(session, code="NZDUSD")

    client = build_test_client(session_factory)

    approved_response = client.post(
        "/api/v1/evaluations",
        json={
            "model_type": "supervised",
            "model_id": model_id,
            "evaluation_type": "validation",
            "confidence": 75.0,
            "risk_to_reward": 2.5,
            "sample_size": 142,
            "max_drawdown": 11.0,
        },
    )
    rejected_response = client.post(
        "/api/v1/evaluations",
        json={
            "model_type": "supervised",
            "model_id": model_id,
            "evaluation_type": "backtest",
            "confidence": 61.0,
            "risk_to_reward": 1.7,
            "sample_size": 44,
            "max_drawdown": 26.0,
            "has_critical_data_issue": True,
        },
    )

    assert approved_response.status_code == 200
    assert rejected_response.status_code == 200
    assert rejected_response.json()["decision"]["approved"] is False

    with session_scope(session_factory) as session:
        approvals = session.query(ApprovedModel).all()
        model = session.get(SupervisedModel, model_id)
        tradeable = is_symbol_tradeable(session, symbol_id=symbol_id)

    assert len(approvals) == 1
    assert approvals[0].is_active is False
    assert approvals[0].revoked_at is not None
    assert model is not None
    assert model.status is ModelStatus.REJECTED
    assert tradeable is False

    approved_symbols_response = client.get("/api/v1/evaluations/approved-symbols", params={"symbol_code": "NZDUSD"})
    reports_response = client.get(
        "/api/v1/evaluations/reports",
        params={"symbol_code": "NZDUSD", "model_type": "supervised", "model_id": model_id},
    )

    assert approved_symbols_response.status_code == 200
    assert approved_symbols_response.json() == []
    assert reports_response.status_code == 200
    assert len(reports_response.json()) == 2
    assert all(report["approved"] is False for report in reports_response.json())
    engine.dispose()


def build_test_client(session_factory) -> TestClient:
    app = FastAPI()
    app.include_router(evaluations_router, prefix="/api/v1")
    app.dependency_overrides[get_api_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[require_authenticated_principal] = lambda: AuthPrincipal(
        subject="test-operator",
        roles=("operator",),
        auth_mode="disabled",
    )

    def override_db() -> Iterator[object]:
        yield from override_db_session(session_factory)

    app.dependency_overrides[get_db_session] = override_db
    return TestClient(app)


def override_db_session(session_factory) -> Iterator[object]:
    with session_scope(session_factory) as session:
        yield session


def seed_supervised_model_fixture(
    session,
    *,
    code: str = "EURUSD",
    version_suffix: str = "v1",
) -> tuple[int, int]:
    symbol = session.query(Symbol).filter(Symbol.code == code).one_or_none()
    if symbol is None:
        symbol = Symbol(code=code, base_currency=code[:3], quote_currency=code[3:], provider="mt5")
        session.add(symbol)
        session.flush()
    feature_set = FeatureSet(
        name="baseline_forex",
        version=f"{code.lower()}-{version_suffix}",
        feature_columns=["close"],
    )
    session.add(feature_set)
    session.flush()
    dataset_version = DatasetVersion(
        symbol_id=symbol.id,
        feature_set_id=feature_set.id,
        status=DatasetStatus.READY,
        version_tag=f"{code.lower()}-dataset-{version_suffix}",
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
        status=ModelStatus.TRAINED,
        model_name="baseline_classifier",
        version_tag=f"{code.lower()}-model-{version_suffix}",
        algorithm="nearest_centroid",
        storage_uri=f".artifacts/{code.lower()}/{version_suffix}/model.json",
    )
    session.add(model)
    session.flush()
    return model.id, symbol.id


def seed_rl_model_fixture(session, *, code: str = "EURUSD") -> tuple[int, int]:
    symbol = Symbol(code=code, base_currency=code[:3], quote_currency=code[3:], provider="mt5")
    session.add(symbol)
    session.flush()
    training_request = TrainingRequest(
        symbol_id=symbol.id,
        dataset_version_id=None,
        training_type=TrainingType.RL,
        status=JobStatus.SUCCEEDED,
        requested_timeframes=["1m", "5m", "15m"],
    )
    session.add(training_request)
    session.flush()
    training_job = RLTrainingJob(
        training_request_id=training_request.id,
        dataset_version_id=None,
        status=JobStatus.SUCCEEDED,
        algorithm="ppo",
        environment_name="ForexTradingEnv",
        metrics={"total_reward": 1.4},
    )
    session.add(training_job)
    session.flush()
    rl_model = RLModel(
        training_job_id=training_job.id,
        symbol_id=symbol.id,
        dataset_version_id=None,
        status=ModelStatus.TRAINED,
        model_name="ppo_policy",
        version_tag=f"{code.lower()}-rl-v1",
        algorithm="ppo",
        storage_uri=f".artifacts/{code.lower()}/ppo.zip",
    )
    session.add(rl_model)
    session.flush()
    return rl_model.id, symbol.id
