"""RL training worker tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from rl_trade_common.settings import Settings
from rl_trade_data import (
    Base,
    DatasetVersion,
    FeatureSet,
    ModelArtifact,
    OHLCCandle,
    RLModel,
    RLTrainingJob,
    Symbol,
    TrainingRequest,
    build_engine,
    build_session_factory,
    session_scope,
)
from rl_trade_data.models import DatasetStatus, JobStatus, Timeframe, TrainingType
from rl_trade_ml import load_ppo_artifacts
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.services.rl_training import perform_rl_training_job
from rl_trade_worker.tasks import run_rl_training_job


def test_perform_rl_training_job_persists_model_metrics_and_artifacts(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'rl_training_worker.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)
    artifacts_dir = tmp_path / ".artifacts"
    progress_events: list[tuple[int, dict[str, object] | None]] = []

    with session_scope(session_factory) as session:
        job_id = seed_rl_training_fixture(session, with_candles=True)

    settings = Settings(_env_file=None, artifacts_root_dir=str(artifacts_dir))
    with session_scope(session_factory) as session:
        result = perform_rl_training_job(
            session=session,
            settings=settings,
            job_id=job_id,
            progress_callback=lambda progress, details=None: progress_events.append((progress, details)),
        )

    with session_scope(session_factory) as session:
        training_job = session.get(RLTrainingJob, job_id)
        training_request = session.get(TrainingRequest, training_job.training_request_id if training_job else -1)
        rl_model = session.scalar(select(RLModel).where(RLModel.training_job_id == job_id))
        artifacts = session.execute(select(ModelArtifact)).scalars().all()

    assert training_job is not None
    assert training_job.metrics is not None
    assert training_job.metrics["device"] == "cpu"
    assert training_job.metrics["model_id"] == rl_model.id
    assert training_request is not None
    assert training_request.status is JobStatus.SUCCEEDED
    assert rl_model is not None
    assert rl_model.status.value == "trained"
    assert rl_model.algorithm == "ppo"
    assert rl_model.storage_uri is not None and rl_model.storage_uri.endswith("checkpoint.zip")
    assert len(artifacts) == 4
    for artifact in artifacts:
        path = Path(artifact.storage_uri)
        assert path.exists()
        if path.suffix == ".json":
            assert json.loads(path.read_text(encoding="utf-8"))
    bundle = load_ppo_artifacts(artifact_dir=result["artifact_dir"])
    assert bundle.model_metadata["algorithm"] == "ppo"
    assert bundle.metrics["device"] == "cpu"
    assert [event[0] for event in progress_events] == [10, 40, 75]
    engine.dispose()


def test_run_rl_training_job_marks_request_failed_when_dataset_rows_cannot_be_built(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'rl_training_failure.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        job_id = seed_rl_training_fixture(session, with_candles=False)

    monkeypatch.setattr("rl_trade_worker.tasks.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("rl_trade_worker.task_base.get_session_factory", lambda: session_factory)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True, raising=False)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False, raising=False)

    result = run_rl_training_job.delay(job_id=job_id)

    assert result.failed()

    with session_scope(session_factory) as session:
        training_job = session.get(RLTrainingJob, job_id)
        training_request = session.get(TrainingRequest, training_job.training_request_id if training_job else -1)

    assert training_job is not None
    assert training_job.status is JobStatus.FAILED
    assert training_job.error_message == "No OHLC candles available for 1m."
    assert training_request is not None
    assert training_request.status is JobStatus.FAILED
    engine.dispose()


def seed_rl_training_fixture(session, *, with_candles: bool) -> int:
    symbol = Symbol(code="GBPUSD", base_currency="GBP", quote_currency="USD", provider="mt5")
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
        row_count=16,
        data_hash="rl-demo-hash",
        details={"indicator_window": 3, "label_horizon_bars": 2, "label_min_move_ratio": "0.0005"},
    )
    session.add(dataset_version)
    session.flush()
    training_request = TrainingRequest(
        symbol_id=symbol.id,
        dataset_version_id=dataset_version.id,
        training_type=TrainingType.RL,
        status=JobStatus.PENDING,
        requested_timeframes=["1m", "5m", "15m"],
    )
    session.add(training_request)
    session.flush()
    training_job = RLTrainingJob(
        training_request_id=training_request.id,
        dataset_version_id=dataset_version.id,
        status=JobStatus.PENDING,
        algorithm="ppo",
        environment_name="ForexTradingEnv",
        hyperparameters={
            "model_name": "ppo_policy",
            "window_size": 4,
            "total_timesteps": 64,
            "n_steps": 16,
            "batch_size": 8,
            "learning_rate": 0.001,
            "gamma": 0.99,
            "seed": 17,
            "atr_feature_name": "atr_3",
            "spread_bps": 0.0,
            "slippage_bps": 0.0,
        },
    )
    session.add(training_job)
    session.flush()

    if with_candles:
        seed_market_candles(session, symbol_id=symbol.id)

    return training_job.id


def seed_market_candles(session, *, symbol_id: int) -> None:
    base_time = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    m1_closes = [
        Decimal("1.2500"),
        Decimal("1.2504"),
        Decimal("1.2508"),
        Decimal("1.2512"),
        Decimal("1.2509"),
        Decimal("1.2514"),
        Decimal("1.2519"),
        Decimal("1.2523"),
        Decimal("1.2520"),
        Decimal("1.2525"),
        Decimal("1.2529"),
        Decimal("1.2533"),
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
                volume=Decimal("120") + Decimal(index),
                provider="mt5",
                source="historical",
            )
        )
        session.flush()

    for minute_offset, open_price, close in [
        (0, Decimal("1.2500"), Decimal("1.2509")),
        (5, Decimal("1.2509"), Decimal("1.2525")),
        (10, Decimal("1.2525"), Decimal("1.2533")),
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
                volume=Decimal("275"),
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
            open=Decimal("1.2495"),
            high=Decimal("1.2538"),
            low=Decimal("1.2490"),
            close=Decimal("1.2533"),
            volume=Decimal("540"),
            provider="mt5",
            source="historical",
        )
    )
    session.flush()
