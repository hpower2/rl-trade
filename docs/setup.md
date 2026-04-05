# Local Setup Runbook

This runbook is the quickest safe path for a new engineer to install the repo, bring up the local surfaces, and run the milestone smoke checks without enabling any live-trading behavior.

## Safety First

- Keep `PAPER_TRADING_ONLY=true`.
- Keep `ALLOW_LIVE_TRADING=false`.
- Do not point the app at a live MetaTrader 5 account.
- Expect the backend to degrade safely when MT5, Redis, PostgreSQL, or GPU support is unavailable.

## 1. Clone And Install

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

## 2. Prepare Environment

Copy `.env.example` to `.env` and keep the safety defaults intact.

```bash
cp .env.example .env
```

Recommended local defaults:

- Keep `APP_ENV=local`.
- Keep `API_AUTH_MODE=disabled` unless you are intentionally testing bearer-token auth.
- Leave `PAPER_TRADING_ONLY=true`.
- Leave `ALLOW_LIVE_TRADING=false`.

If host ports are already taken, override these values in `.env`:

- `POSTGRES_HOST_PORT`
- `REDIS_HOST_PORT`
- `API_HOST_PORT`
- `FRONTEND_HOST_PORT`

## 3. Run The Main Local Surfaces

### Local Python Processes

```bash
make run-api
make run-worker
make run-scheduler
make run-frontend
```

### Docker Compose Stack

Use this path when you want PostgreSQL, Redis, API, workers, and frontend started together.

```bash
docker compose config
make compose-build
docker compose up -d
make validate-compose-runtime
```

For GPU-backed training validation, use the GPU override only on a host with NVIDIA container runtime support:

```bash
make validate-compose-gpu-host
docker compose -f compose.yaml -f docker/compose.gpu.yaml up -d
make validate-compose-gpu-runtime
```

## 4. Run Milestone Smoke Checks

### Core Backend Workflow

```bash
make validate-core-smoke
```

This probes `/health`, `/health/db`, `/health/redis`, and `/api/v1/system/status`, then runs the seeded validate, ingest, preprocess, train, evaluate, approve, and demo-only paper-trade flow.

### Paper-Trading Dry Run

```bash
PYTHONPATH=apps/api/src:libs/common/src:libs/data/src:libs/trading/src python -m rl_trade_api.tools.paper_trading_dry_run
```

### WebSocket Event Dry Run

```bash
PYTHONPATH=apps/api/src:apps/worker/src:libs/common/src:libs/data/src:libs/features/src:libs/ml/src:libs/trading/src python -m rl_trade_api.tools.websocket_event_dry_run
```

### Frontend Browser Smoke

```bash
npm run frontend:test
npm run frontend:test:e2e
```

### One-Command Milestone Checkpoint

```bash
make validate-milestone15
```

Use this when you want the repo's current Milestone 15 validation bundle in one pass instead of running the backend and frontend smoke commands separately.

### Clean Setup Proof

```bash
make validate-clean-setup
```

Use this when you want to follow the documented install path in a temporary workspace from a clean `.env` copy through backend install, frontend install, Playwright browser install, and the frontend unit smoke suite.

## 5. Quick Validation Checklist

- `make validate-clean-setup`
- `make test-backend`
- `make validate-backend`
- `make validate-frontend`
- `make validate-core-smoke`
- `make validate-milestone15`
- `npm run frontend:test:e2e`

## 6. When Something Fails

- Re-check `.env` against `.env.example`.
- Confirm PostgreSQL and Redis host/port values match the path you are using.
- If MT5 is unavailable, expect MT5-dependent routes to stay blocked instead of failing open.
- If CUDA is unavailable, use the base Compose stack and expect the training worker to log a safe CPU fallback.
- See the root `README.md` troubleshooting section for the current port, auth, MT5, and GPU notes.
