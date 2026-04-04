"""Supervised training worker tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from rl_trade_common.settings import Settings
from rl_trade_ml import load_supervised_artifacts
from rl_trade_data import (
    Base,
    DatasetVersion,
    FeatureSet,
    ModelArtifact,
    OHLCCandle,
    SupervisedModel,
    SupervisedTrainingJob,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import DatasetStatus, JobStatus, Timeframe, TrainingType
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.services.supervised_training import perform_supervised_training_job
from rl_trade_worker.tasks import run_supervised_training_job


def test_perform_supervised_training_job_persists_model_metrics_and_artifacts(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_worker.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    artifacts_dir = tmp_path / ".artifacts"
    progress_events: list[tuple[int, dict[str, object] | None]] = []

    with session_scope(session_factory) as session:
        job_id = seed_training_fixture(session, with_candles=True)

    settings = Settings(_env_file=None, artifacts_root_dir=str(artifacts_dir))
    with session_scope(session_factory) as session:
        result = perform_supervised_training_job(
            session=session,
            settings=settings,
            job_id=job_id,
            progress_callback=lambda progress, details=None: progress_events.append((progress, details)),
        )

    with session_scope(session_factory) as session:
        training_job = session.get(SupervisedTrainingJob, job_id)
        assert training_job is not None
        training_request = session.get(TrainingRequest, training_job.training_request_id)
        supervised_model = session.scalar(select(SupervisedModel).where(SupervisedModel.training_job_id == job_id))
        artifacts = session.execute(select(ModelArtifact)).scalars().all()

    assert training_job.metrics is not None
    assert training_job.metrics["device"] == "cpu"
    assert training_job.metrics["model_id"] == supervised_model.id
    assert training_request is not None
    assert training_request.status is JobStatus.SUCCEEDED
    assert supervised_model is not None
    assert supervised_model.status.value == "trained"
    assert supervised_model.algorithm in {"majority_class", "nearest_centroid"}
    assert len(artifacts) == 4
    for artifact in artifacts:
        path = Path(artifact.storage_uri)
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8"))
    assert [event[0] for event in progress_events] == [10, 40, 75]
    engine.dispose()


def test_perform_supervised_training_job_supports_torch_mlp_checkpoint_artifacts(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_torch.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    artifacts_dir = tmp_path / ".artifacts"

    with session_scope(session_factory) as session:
        job_id = seed_training_fixture(
            session,
            with_candles=True,
            algorithm="torch_mlp",
            hyperparameters={
                "model_name": "torch_classifier",
                "validation_ratio": 0.25,
                "walk_forward_folds": 2,
                "hidden_dim": 8,
                "epochs": 10,
                "learning_rate": 0.02,
            },
        )

    settings = Settings(_env_file=None, artifacts_root_dir=str(artifacts_dir))
    with session_scope(session_factory) as session:
        result = perform_supervised_training_job(
            session=session,
            settings=settings,
            job_id=job_id,
        )

    with session_scope(session_factory) as session:
        training_job = session.get(SupervisedTrainingJob, job_id)
        model = session.scalar(select(SupervisedModel).where(SupervisedModel.training_job_id == job_id))
        artifacts = session.execute(select(ModelArtifact)).scalars().all()

    assert training_job is not None
    assert training_job.metrics is not None
    assert training_job.metrics["device"] in {"cpu", "cuda"}
    assert model is not None
    assert model.algorithm == "torch_mlp"
    assert model.storage_uri is not None and model.storage_uri.endswith("checkpoint.pt")
    assert any(Path(artifact.storage_uri).suffix == ".pt" for artifact in artifacts)
    bundle = load_supervised_artifacts(artifact_dir=result["artifact_dir"])
    assert bundle.model_state["algorithm"] == "torch_mlp"
    assert bundle.model_state["state_dict"]
    engine.dispose()


def test_run_supervised_training_job_marks_request_failed_when_dataset_rows_cannot_be_built(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'supervised_training_failure.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        job_id = seed_training_fixture(session, with_candles=False)

    monkeypatch.setattr("rl_trade_worker.tasks.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("rl_trade_worker.task_base.get_session_factory", lambda: session_factory)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True, raising=False)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False, raising=False)

    result = run_supervised_training_job.delay(job_id=job_id)

    assert result.failed()

    with session_scope(session_factory) as session:
        training_job = session.get(SupervisedTrainingJob, job_id)
        training_request = session.get(TrainingRequest, training_job.training_request_id if training_job else -1)

    assert training_job is not None
    assert training_job.status is JobStatus.FAILED
    assert training_job.error_message == "No OHLC candles available for 1m."
    assert training_request is not None
    assert training_request.status is JobStatus.FAILED
    engine.dispose()


def seed_training_fixture(
    session,
    *,
    with_candles: bool,
    algorithm: str = "auto_baseline",
    hyperparameters: dict[str, object] | None = None,
) -> int:
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
        row_count=16,
        data_hash="demo-hash",
        details={"indicator_window": 3, "label_horizon_bars": 2, "label_min_move_ratio": "0.0005"},
    )
    session.add(dataset_version)
    session.flush()
    training_request = TrainingRequest(
        symbol_id=symbol.id,
        dataset_version_id=dataset_version.id,
        training_type=TrainingType.SUPERVISED,
        status=JobStatus.PENDING,
        requested_timeframes=["1m", "5m", "15m"],
    )
    session.add(training_request)
    session.flush()
    training_job = SupervisedTrainingJob(
        training_request_id=training_request.id,
        dataset_version_id=dataset_version.id,
        status=JobStatus.PENDING,
        algorithm=algorithm,
        hyperparameters=hyperparameters or {"model_name": "baseline_classifier", "validation_ratio": 0.25, "walk_forward_folds": 2},
    )
    session.add(training_job)
    session.flush()

    if with_candles:
        seed_market_candles(session, symbol_id=symbol.id)

    return training_job.id


def seed_market_candles(session, *, symbol_id: int) -> None:
    base_time = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    m1_closes = [
        Decimal("1.1000"),
        Decimal("1.1004"),
        Decimal("1.1008"),
        Decimal("1.1012"),
        Decimal("1.1016"),
        Decimal("1.1020"),
        Decimal("1.1024"),
        Decimal("1.1028"),
        Decimal("1.1032"),
        Decimal("1.1036"),
        Decimal("1.1040"),
        Decimal("1.1044"),
    ]

    for index, close in enumerate(m1_closes):
        open_price = close - Decimal("0.0002")
        session.add(
            OHLCCandle(
                symbol_id=symbol_id,
                timeframe=Timeframe.M1,
                candle_time=base_time + timedelta(minutes=index),
                open=open_price,
                high=close + Decimal("0.0003"),
                low=open_price - Decimal("0.0003"),
                close=close,
                volume=Decimal("100") + Decimal(index),
                provider="mt5",
                source="historical",
            )
        )
        session.flush()

    for minute_offset, open_price, close in [
        (0, Decimal("1.1000"), Decimal("1.1016")),
        (5, Decimal("1.1016"), Decimal("1.1036")),
        (10, Decimal("1.1036"), Decimal("1.1044")),
    ]:
        session.add(
            OHLCCandle(
                symbol_id=symbol_id,
                timeframe=Timeframe.M5,
                candle_time=base_time + timedelta(minutes=minute_offset),
                open=open_price,
                high=close + Decimal("0.0004"),
                low=open_price - Decimal("0.0004"),
                close=close,
                volume=Decimal("250"),
                provider="mt5",
                source="historical",
            )
        )
        session.flush()

    session.add(
        OHLCCandle(
            symbol_id=symbol_id,
            timeframe=Timeframe.M15,
            candle_time=base_time,
            open=Decimal("1.0995"),
            high=Decimal("1.1050"),
            low=Decimal("1.0990"),
            close=Decimal("1.1044"),
            volume=Decimal("500"),
            provider="mt5",
            source="historical",
        )
    )
    session.flush()
