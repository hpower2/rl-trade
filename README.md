# Forex Trainer & Paper Trading Dashboard

Production-style monorepo scaffold for a Forex Trainer & Paper Trading Dashboard with a FastAPI backend, Celery workers, shared Python libraries, and a React/Vite frontend.

## Architecture

- `apps/api`: FastAPI application entry point and HTTP surface.
- `apps/worker`: Celery worker bootstrap and task wiring surface.
- `apps/frontend`: React + TypeScript + Vite dashboard shell.
- `libs/common`: shared settings, safety guards, and logging.
- `libs/data`: future data-access and persistence helpers.
- `libs/features`: future feature engineering modules.
- `libs/ml`: future model training and evaluation modules.
- `libs/trading`: future MT5 and paper-trading integrations.
- `docker`: container assets and Compose files.
- `docs`: lightweight architecture and setup notes.

## Setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### Frontend

```bash
npm install
```

### Local commands

```bash
make test-backend
make validate-backend
make validate-db
make validate-db-timescale
make db-upgrade
make validate-frontend
make run-api
make run-worker
make run-scheduler
make run-frontend
```

Copy `.env.example` to `.env` before connecting real infrastructure. Safety checks keep live trading disabled by default.

For local Milestone 3 API work, auth defaults to `API_AUTH_MODE=disabled`. Use `API_AUTH_MODE=static_token` plus `API_AUTH_TOKEN=...` when you want bearer-token protection, and note that `staging` and `prod` reject disabled API auth at settings load time.

For the Milestone 4 worker runtime, `WORKER_QUEUES`, `WORKER_CONCURRENCY`, and `WORKER_PREFETCH_MULTIPLIER` control the Celery worker entry point, while `SCHEDULER_HEARTBEAT_INTERVAL_SECONDS` and `SCHEDULER_MAX_INTERVAL_SECONDS` control the beat scheduler's maintenance heartbeat cadence.
