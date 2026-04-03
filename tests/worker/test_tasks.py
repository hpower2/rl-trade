"""Worker queue and tracked task tests."""

from __future__ import annotations

import logging

from rl_trade_data import Base, IngestionJob, JobStatus, Symbol, build_engine, build_session_factory, session_scope
from rl_trade_worker.celery_app import celery_app
from rl_trade_worker.queues import ALL_QUEUE_NAMES, INGESTION_QUEUE, MAINTENANCE_QUEUE, PREPROCESSING_QUEUE
from rl_trade_worker.tasks import run_ingestion_probe


def test_celery_queue_configuration_exposes_named_queues() -> None:
    queue_names = {queue.name for queue in celery_app.conf.task_queues}

    assert queue_names == set(ALL_QUEUE_NAMES)
    assert celery_app.conf.task_default_queue == MAINTENANCE_QUEUE
    assert celery_app.conf.task_routes["jobs.run_ingestion_probe"]["queue"] == INGESTION_QUEUE
    assert celery_app.conf.task_routes["jobs.run_preprocessing_job"]["queue"] == PREPROCESSING_QUEUE


def test_tracked_task_success_and_retry_paths_update_job_state(tmp_path, monkeypatch, caplog) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'worker_retry.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="AUDUSD", base_currency="AUD", quote_currency="USD")
        session.add(symbol)
        session.flush()
        job = IngestionJob(symbol_id=symbol.id, requested_timeframes=["1m"])
        session.add(job)
        session.flush()
        job_id = job.id

    monkeypatch.setattr("rl_trade_worker.task_base.get_session_factory", lambda: session_factory)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True, raising=False)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False, raising=False)
    caplog.set_level(logging.WARNING)

    result = run_ingestion_probe.delay(job_id=job_id, fail_until_attempt=1)

    assert result.successful()

    with session_scope(session_factory) as session:
        stored_job = session.get(IngestionJob, job_id)

    assert stored_job is not None
    assert stored_job.status == JobStatus.SUCCEEDED
    assert stored_job.progress_percent == 100
    assert stored_job.started_at is not None
    assert stored_job.finished_at is not None
    assert stored_job.details["phase"] == "completed"
    assert stored_job.details["retry_count"] == 1
    assert stored_job.details["last_retry_reason"] == "transient probe failure"
    engine.dispose()


def test_tracked_task_failure_marks_job_failed(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'worker_failure.sqlite'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine=engine)

    with session_scope(session_factory) as session:
        symbol = Symbol(code="NZDUSD", base_currency="NZD", quote_currency="USD")
        session.add(symbol)
        session.flush()
        job = IngestionJob(symbol_id=symbol.id, requested_timeframes=["5m"])
        session.add(job)
        session.flush()
        job_id = job.id

    monkeypatch.setattr("rl_trade_worker.task_base.get_session_factory", lambda: session_factory)
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True, raising=False)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", False, raising=False)

    result = run_ingestion_probe.delay(job_id=job_id, fail_hard=True)

    assert result.failed()

    with session_scope(session_factory) as session:
        stored_job = session.get(IngestionJob, job_id)

    assert stored_job is not None
    assert stored_job.status == JobStatus.FAILED
    assert stored_job.error_message == "permanent probe failure"
    engine.dispose()
