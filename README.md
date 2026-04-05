# Forex Trainer & Paper Trading Dashboard

Production-style monorepo scaffold for a Forex Trainer & Paper Trading Dashboard with a FastAPI backend, Celery workers, shared Python libraries, and a React/Vite frontend.

For a clean local bring-up path that goes from install to smoke validation, use [docs/setup.md](/Users/irvineafridwicahya/personal/rl-trade/docs/setup.md).

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

## Safety Guarantees

- Demo trading only: live trading stays disabled by default and must not be enabled.
- Backend-enforced broker safety: live MT5 accounts are blocked in backend code, not just in the UI.
- Backend-enforced trade gating: a symbol cannot be paper traded unless it has an approved model.
- Approval thresholds are enforced before tradeability: confidence must be at least `70%` and risk-to-reward must be at least `2.0`.
- Fail-safe dependency handling: MT5, Redis, database, and GPU failures degrade features safely instead of failing open.
- Long-running ingestion, preprocessing, training, evaluation, and trading loops run through workers rather than API request handlers.

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
npx playwright install --with-deps chromium
```

### Local commands

```bash
make test-backend
make validate-backend
make validate-db
make validate-db-timescale
make db-upgrade
make validate-frontend
make validate-core-smoke
make validate-clean-setup
make validate-milestone15
make run-api
make run-worker
make run-scheduler
make run-frontend
npm run frontend:test
npm run frontend:test:e2e
PYTHONPATH=apps/api/src:libs/common/src:libs/data/src:libs/trading/src python -m rl_trade_api.tools.paper_trading_dry_run
PYTHONPATH=apps/api/src:apps/worker/src:libs/common/src:libs/data/src:libs/features/src:libs/ml/src:libs/trading/src python -m rl_trade_api.tools.websocket_event_dry_run
```

Copy `.env.example` to `.env` before connecting real infrastructure. Safety checks keep live trading disabled by default.

For local Milestone 3 API work, auth defaults to `API_AUTH_MODE=disabled`. Use `API_AUTH_MODE=static_token` plus `API_AUTH_TOKEN=...` when you want bearer-token protection, and note that `staging` and `prod` reject disabled API auth at settings load time.

For the split worker runtime, local Python processes use `WORKER_QUEUES`, `WORKER_CONCURRENCY`, and `WORKER_PREFETCH_MULTIPLIER`, while the Docker Compose stack exposes separate `CPU_WORKER_*` and `TRAINING_WORKER_*` overrides so the general worker and the dedicated training lane can be tuned independently. `SCHEDULER_HEARTBEAT_INTERVAL_SECONDS` and `SCHEDULER_MAX_INTERVAL_SECONDS` control the beat scheduler's maintenance heartbeat cadence in both cases.

For the Milestone 11 manual paper-trading smoke path, run `python -m rl_trade_api.tools.paper_trading_dry_run` with the backend `PYTHONPATH` shown above. The dry run uses an in-memory FastAPI test surface, a temporary SQLite database, and a demo-only fake MT5 gateway so it exercises the current paper-trading workflow without touching real broker infrastructure.

For the Milestone 12 manual live-update smoke path, run `python -m rl_trade_api.tools.websocket_event_dry_run` with the expanded `PYTHONPATH` shown above. The dry run opens `/ws/events` against a temporary FastAPI app, runs eager ingestion and supervised-training jobs, and prints the live WebSocket status sequence for both flows.

For the Milestone 15 core backend smoke path, run `make validate-core-smoke`. That dry run builds a temporary FastAPI app plus SQLite workspace, probes `/health`, `/health/db`, `/health/redis`, and `/api/v1/system/status`, validates `EURUSD`, ingests seeded candles through the eager worker path, preprocesses a dataset, trains and evaluates a supervised model, confirms approval gating, and then opens a demo-only paper-trade flow through the real trading routes.

For the frontend browser smoke path, run `npm run frontend:test:e2e`. The Playwright suite serves the built Vite app locally, seeds operator state with the repo fixtures under `apps/frontend/tests/e2e/fixtures`, and exercises the critical happy path from login through symbol validation, training request submission, approval visibility, and paper-trading runtime controls without requiring a live backend.

For a repeatable Milestone 15 checkpoint, run `make validate-milestone15`. That command bundles the docs/workflow smoke checks, API health plus core backend smoke coverage, the curated backend hardening regression lane, and the frontend unit plus Playwright browser smoke suites.

For an isolated setup proof that follows the documented install path in a temporary workspace, run `make validate-clean-setup`. That command copies the repo into a scratch directory, copies `.env.example` to `.env`, creates a fresh virtualenv, installs the editable backend package, validates backend bootstrap, installs frontend dependencies, installs Playwright Chromium, and runs the frontend unit smoke suite.

## Environment Variables

Copy `.env.example` to `.env` and treat it as the single local override file for backend processes and Docker Compose defaults.

### Runtime and auth

- `APP_ENV`: application environment. Keep `local` for workstation development; `staging` and `prod` require API auth.
- `LOG_LEVEL`, `LOG_FORMAT`: shared logging verbosity and output format for API, workers, and scheduler.
- `API_HOST`, `API_PORT`, `FRONTEND_PORT`: local process bind ports outside Docker Compose.
- `API_AUTH_MODE`, `API_AUTH_TOKEN`, `API_AUTH_SUBJECT`: API auth controls. `static_token` requires a non-empty token.

### Data, queues, and artifacts

- `DATABASE_URL`, `REDIS_URL`: primary backend connection strings for local Python processes.
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: optional Celery overrides; when left empty they fall back to `REDIS_URL`.
- `CPU_WORKER_QUEUES`, `CPU_WORKER_CONCURRENCY`, `CPU_WORKER_PREFETCH_MULTIPLIER`: Compose overrides for the general worker lane.
- `TRAINING_WORKER_QUEUES`, `TRAINING_WORKER_CONCURRENCY`, `TRAINING_WORKER_PREFETCH_MULTIPLIER`: Compose overrides for the dedicated supervised and RL training lane.
- `SCHEDULER_HEARTBEAT_INTERVAL_SECONDS`, `SCHEDULER_MAX_INTERVAL_SECONDS`: scheduler maintenance cadence.
- `ARTIFACTS_ROOT_DIR`: shared artifact/output directory for models and generated files.

### MT5 and safety gates

- `MT5_TERMINAL_PATH`, `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`: MT5 integration settings. Missing or invalid values degrade MT5-dependent features safely instead of enabling live trading.
- `PAPER_TRADING_ONLY`: must stay `true`.
- `ALLOW_LIVE_TRADING`: must stay `false`.
- `MODEL_APPROVAL_MIN_CONFIDENCE`, `MODEL_APPROVAL_MIN_RISK_REWARD`, `MODEL_APPROVAL_MIN_SAMPLE_SIZE`, `MODEL_APPROVAL_MAX_DRAWDOWN`: backend approval thresholds enforced before any symbol can become tradeable.

### Docker Compose and GPU overrides

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: Compose database bootstrap values.
- `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `FRONTEND_HOST_PORT`: host-published port overrides when default ports are already in use. The Compose stack keeps the API on the internal Docker network and exposes the frontend host port only.
- `TRAINING_WORKER_REQUIRE_CUDA`: fail closed for the Compose `training_worker` when a GPU is expected but unavailable.
- `TRAINING_WORKER_NVIDIA_VISIBLE_DEVICES`, `TRAINING_WORKER_GPUS`: optional NVIDIA runtime selectors for the GPU override stack.

## Troubleshooting

- API auth fails at startup in `staging` or `prod`:
  Set `API_AUTH_MODE=static_token` and provide `API_AUTH_TOKEN`. Disabled auth is rejected by settings validation outside local and dev-style workflows.
- Compose services cannot reach Postgres or Redis:
  Inside Docker Compose, use the container hostnames from `compose.yaml` defaults such as `postgres` and `redis`, not `localhost`.
- Host ports `5432`, `6379`, or `4173` are already taken:
  Override `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, and `FRONTEND_HOST_PORT` instead of editing in-container service ports.
- Docker Compose frontend cannot reach the API directly from the browser:
  That is expected now. Use the frontend host port and let the frontend reverse proxy `/api` and `/ws` traffic to the internal `api` service.
- The GPU override stack does not start cleanly:
  Run `make validate-compose-gpu-host` first, then boot with `docker compose -f compose.yaml -f docker/compose.gpu.yaml up -d`, and finish with `make validate-compose-gpu-runtime`.
- `training_worker` falls back to CPU:
  That is expected on non-GPU hosts. Keep the base `compose.yaml` path unless you intentionally require CUDA and have NVIDIA container support configured.
- MT5-dependent routes report degraded status:
  Check `MT5_TERMINAL_PATH`, `MT5_LOGIN`, and `MT5_SERVER`. The backend is designed to fail safely and keep paper-trading protections active when MT5 is unavailable.
