"""Named Celery queues and routing rules."""

from __future__ import annotations

from kombu import Queue

INGESTION_QUEUE = "ingestion"
PREPROCESSING_QUEUE = "preprocessing"
SUPERVISED_TRAINING_QUEUE = "supervised_training"
RL_TRAINING_QUEUE = "rl_training"
EVALUATION_QUEUE = "evaluation"
TRADING_QUEUE = "trading"
MAINTENANCE_QUEUE = "maintenance"

ALL_QUEUE_NAMES = (
    INGESTION_QUEUE,
    PREPROCESSING_QUEUE,
    SUPERVISED_TRAINING_QUEUE,
    RL_TRAINING_QUEUE,
    EVALUATION_QUEUE,
    TRADING_QUEUE,
    MAINTENANCE_QUEUE,
)

TASK_QUEUES = tuple(Queue(name) for name in ALL_QUEUE_NAMES)

TASK_ROUTES = {
    "system.ping": {"queue": MAINTENANCE_QUEUE},
    "jobs.run_ingestion_probe": {"queue": INGESTION_QUEUE},
    "jobs.run_ingestion_job": {"queue": INGESTION_QUEUE},
    "jobs.run_preprocessing_job": {"queue": PREPROCESSING_QUEUE},
}
