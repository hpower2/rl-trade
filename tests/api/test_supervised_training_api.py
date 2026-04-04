"""Supervised training request API tests."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import select

from rl_trade_api.api.deps import get_db_session
from rl_trade_api.app import create_app
from rl_trade_data import (
    Base,
    DatasetVersion,
    FeatureSet,
    JobStatus,
    ModelArtifact,
    SupervisedModel,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import ArtifactType, DatasetStatus, ModelStatus, Timeframe, TrainingType


def test_supervised_training_request_endpoint_creates_job_and_enqueues_worker(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_request.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURUSD", base_currency="EUR", quote_currency="USD", provider="mt5")
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
            row_count=12,
            data_hash="abc123",
            details={"indicator_window": 3, "label_horizon_bars": 2, "label_min_move_ratio": "0.0005"},
        )
        session.add(dataset_version)
        session.flush()
        dataset_version_id = dataset_version.id

    app = create_app()
    enqueued: dict[str, int] = {}

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        "rl_trade_api.services.training.run_supervised_training_job.delay",
        lambda *, job_id: enqueued.setdefault("job_id", job_id),
    )
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

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

    assert response.status_code == 200
    assert response.json()["symbol_code"] == "EURUSD"
    assert response.json()["algorithm"] == "auto_baseline"
    assert response.json()["status"] == "pending"

    with session_scope(session_factory) as session:
        training_request = session.scalar(select(TrainingRequest))
        training_job = session.scalar(select(SupervisedTrainingJob))

    assert training_request is not None
    assert training_request.training_type is TrainingType.SUPERVISED
    assert training_request.dataset_version_id == dataset_version_id
    assert training_job is not None
    assert training_job.dataset_version_id == dataset_version_id
    assert training_job.hyperparameters == {
        "model_name": "baseline_classifier",
        "validation_ratio": 0.25,
        "walk_forward_folds": 2,
        "hidden_dim": 16,
        "epochs": 25,
        "learning_rate": 0.01,
    }
    assert enqueued["job_id"] == training_job.id
    assert "/api/v1/training/supervised/request" in app.openapi()["paths"]
    engine.dispose()


def test_supervised_training_request_endpoint_rejects_non_ready_dataset(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_not_ready.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="GBPUSD", base_currency="GBP", quote_currency="USD", provider="mt5")
        session.add(symbol)
        session.flush()
        feature_set = FeatureSet(name="baseline_forex", version="v1", feature_columns=["close"])
        session.add(feature_set)
        session.flush()
        dataset_version = DatasetVersion(
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            status=DatasetStatus.PENDING,
            version_tag="trade_setup-pending",
            primary_timeframe=Timeframe.M1,
            included_timeframes=["1m", "5m", "15m"],
            label_name="trade_setup_direction",
        )
        session.add(dataset_version)
        session.flush()
        dataset_version_id = dataset_version.id

    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post(
        "/api/v1/training/supervised/request",
        json={"dataset_version_id": dataset_version_id},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": "http_error",
        "message": f"Dataset version {dataset_version_id} is not ready for training.",
        "details": [],
    }
    engine.dispose()


def test_supervised_training_status_endpoint_returns_model_and_artifacts(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_status.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="USDCHF", base_currency="USD", quote_currency="CHF", provider="mt5")
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
            requested_timeframes=["1m", "5m", "15m"],
        )
        session.add(training_request)
        session.flush()
        training_job = SupervisedTrainingJob(
            training_request_id=training_request.id,
            dataset_version_id=dataset_version.id,
            algorithm="nearest_centroid",
            status="succeeded",
            progress_percent=100,
            metrics={"validation_accuracy": 0.75, "device": "cpu"},
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
            version_tag="trade_setup-demo-nearest_centroid",
            algorithm="nearest_centroid",
            storage_uri="/tmp/model.json",
            inference_config={"output_classes": ["buy", "sell", "no_trade"]},
        )
        session.add(model)
        session.flush()
        session.add(
            ModelArtifact(
                supervised_model_id=model.id,
                artifact_type=ArtifactType.CHECKPOINT,
                storage_uri="/tmp/model.json",
                checksum="abc123",
                size_bytes=128,
                details={"algorithm": "nearest_centroid"},
            )
        )
        session.flush()
        job_id = training_job.id

    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.get(f"/api/v1/training/supervised/{job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["metrics"]["device"] == "cpu"
    assert response.json()["model"]["algorithm"] == "nearest_centroid"
    assert response.json()["artifacts"][0]["artifact_type"] == "checkpoint"
    assert "/api/v1/training/supervised/{job_id}" in app.openapi()["paths"]
    engine.dispose()


def test_supervised_training_retry_requeues_failed_job_and_cleans_partial_model(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_retry.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="EURGBP", base_currency="EUR", quote_currency="GBP", provider="mt5")
        session.add(symbol)
        session.flush()
        feature_set = FeatureSet(name="baseline_forex", version="v1", feature_columns=["close"])
        session.add(feature_set)
        session.flush()
        dataset_version = DatasetVersion(
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            status=DatasetStatus.READY,
            version_tag="trade_setup-failed",
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
            status="failed",
            requested_timeframes=["1m", "5m", "15m"],
        )
        session.add(training_request)
        session.flush()
        training_job = SupervisedTrainingJob(
            training_request_id=training_request.id,
            dataset_version_id=dataset_version.id,
            algorithm="nearest_centroid",
            status="failed",
            progress_percent=75,
            metrics={"validation_accuracy": 0.25},
            error_message="sample failure",
        )
        session.add(training_job)
        session.flush()
        model = SupervisedModel(
            training_job_id=training_job.id,
            symbol_id=symbol.id,
            dataset_version_id=dataset_version.id,
            feature_set_id=feature_set.id,
            status=ModelStatus.TRAINING,
            model_name="baseline_classifier",
            version_tag="partial-model",
            algorithm="nearest_centroid",
            storage_uri="/tmp/partial-model.json",
        )
        session.add(model)
        session.flush()
        session.add(
            ModelArtifact(
                supervised_model_id=model.id,
                artifact_type=ArtifactType.REPORT,
                storage_uri="/tmp/partial-report.json",
                checksum="retry-me",
                size_bytes=64,
                details={"phase": "failed"},
            )
        )
        session.flush()
        job_id = training_job.id

    app = create_app()
    enqueued: dict[str, int] = {}

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        "rl_trade_api.services.training.run_supervised_training_job.delay",
        lambda *, job_id: enqueued.setdefault("job_id", job_id),
    )
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post(f"/api/v1/training/supervised/{job_id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["supervised_training_job_id"] == job_id

    with session_scope(session_factory) as session:
        training_job = session.get(SupervisedTrainingJob, job_id)
        training_request = session.scalar(select(TrainingRequest))
        model = session.scalar(select(SupervisedModel).where(SupervisedModel.training_job_id == job_id))
        artifacts = session.execute(select(ModelArtifact)).scalars().all()

    assert training_job is not None
    assert training_job.status is JobStatus.PENDING
    assert training_job.progress_percent == 0
    assert training_job.error_message is None
    assert training_job.metrics is None
    assert training_job.started_at is None
    assert training_job.finished_at is None
    assert training_request is not None
    assert training_request.status is JobStatus.PENDING
    assert model is None
    assert artifacts == []
    assert enqueued["job_id"] == job_id
    engine.dispose()


def test_supervised_training_retry_rejects_non_failed_job(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_retry_conflict.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="AUDJPY", base_currency="AUD", quote_currency="JPY", provider="mt5")
        session.add(symbol)
        session.flush()
        feature_set = FeatureSet(name="baseline_forex", version="v1", feature_columns=["close"])
        session.add(feature_set)
        session.flush()
        dataset_version = DatasetVersion(
            symbol_id=symbol.id,
            feature_set_id=feature_set.id,
            status=DatasetStatus.READY,
            version_tag="trade_setup-ready",
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
        training_job = SupervisedTrainingJob(
            training_request_id=training_request.id,
            dataset_version_id=dataset_version.id,
            algorithm="auto_baseline",
            status=JobStatus.RUNNING,
        )
        session.add(training_job)
        session.flush()
        job_id = training_job.id

    app = create_app()

    def override_db_session() -> Iterator[object]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.post(f"/api/v1/training/supervised/{job_id}/retry")

    assert response.status_code == 409
    assert response.json() == {
        "error": "http_error",
        "message": f"Supervised training job {job_id} cannot be retried from status running.",
        "details": [],
    }
    engine.dispose()
