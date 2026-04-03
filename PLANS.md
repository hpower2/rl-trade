# PLANS.md

## Goal
Build a production-style MVP for a Forex Trainer & Paper Trading Dashboard that can:

- validate forex symbols
- ingest OHLC data for 1m / 5m / 15m
- store time-series data in PostgreSQL + TimescaleDB
- preprocess candles into reusable features and labels
- train supervised and RL models
- evaluate and approve models using strict thresholds
- connect to MetaTrader 5 Demo account only
- paper trade only symbols with approved models
- monitor jobs, models, signals, positions, and equity from a dashboard

---

## Current status
- [x] Milestone 1: Monorepo scaffold and shared configuration
- [x] Milestone 2: Database schema, TimescaleDB setup, and migrations
- [x] Milestone 3: API foundation, auth skeleton, and health endpoints
- [x] Milestone 4: Worker foundation, Celery queues, and job state tracking
- [x] Milestone 5: Symbol validation and MT5 connectivity foundation
- [x] Milestone 6: OHLC ingestion pipeline for 1m / 5m / 15m
- [x] Milestone 7: Feature engineering and dataset versioning
- [ ] Milestone 8: Supervised training pipeline
- [ ] Milestone 9: RL environment and RL training pipeline
- [ ] Milestone 10: Evaluation, approval gating, and model registry
- [ ] Milestone 11: Paper trading engine and backend enforcement
- [ ] Milestone 12: WebSocket events and realtime progress updates
- [ ] Milestone 13: Frontend dashboard pages and workflows
- [ ] Milestone 14: Docker Compose, GPU wiring, and runtime validation
- [ ] Milestone 15: Seed data, smoke tests, docs, and final hardening

---

## Milestones

### Milestone 1: Monorepo scaffold and shared configuration
**Scope**
- Create repo structure:
  - `/apps/frontend`
  - `/apps/api`
  - `/apps/worker`
  - `/libs/common`
  - `/libs/data`
  - `/libs/features`
  - `/libs/ml`
  - `/libs/trading`
  - `/docker`
  - `/docs`
- Add root README
- Add `.env.example`
- Add Python dependency management files
- Add frontend package files
- Add shared settings/config module
- Add logging setup
- Add base Makefile or task runner commands if useful

**Done when**
- Repo has a clean monorepo layout
- API, worker, and frontend all have bootstrapped entry points
- Shared config can load environment variables cleanly
- Logging and settings are centralized
- Repo can be installed without unresolved imports

**Validation**
- Backend import smoke test passes
- Frontend install/build scaffolding works
- `.env.example` covers required settings
- Basic README setup section exists

**Progress notes**
- 2026-04-03: Bootstrapped the monorepo folder layout, root Python/npm workspace config, shared settings/logging module, API and worker entry points, frontend Vite shell, and baseline docs.
- 2026-04-03: Validated editable backend install, backend import smoke, and frontend production build; Milestone 1 is complete.
- 2026-04-03: Added backend safety/bootstrap tests and a repeatable `make test-backend` check so Milestone 1 validation covers critical paper-trading safeguards.

---

### Milestone 2: Database schema, TimescaleDB setup, and migrations
**Scope**
- Configure PostgreSQL connection
- Enable TimescaleDB extension
- Create initial SQLAlchemy models and Alembic migrations for:
  - symbols
  - symbol_validation_results
  - ohlc_candles
  - ingestion_jobs
  - preprocessing_jobs
  - feature_sets
  - dataset_versions
  - training_requests
  - supervised_training_jobs
  - rl_training_jobs
  - supervised_models
  - rl_models
  - model_artifacts
  - model_evaluations
  - approved_models
  - mt5_accounts
  - paper_trade_signals
  - paper_trade_orders
  - paper_trade_positions
  - trade_executions
  - equity_snapshots
  - audit_logs
  - system_logs
- Add Timescale hypertable migration for `ohlc_candles`
- Add unique/index constraints for candle deduplication and job lookup

**Done when**
- DB schema is represented in models and migrations
- `ohlc_candles` is hypertable-enabled
- OHLC uniqueness is enforced on `(symbol, timeframe, candle_time)`
- Core tables can be created end-to-end in a fresh DB

**Validation**
- Alembic migration up succeeds on clean database
- Alembic downgrade/upgrade path works for initial migration
- DB inspection confirms hypertable and indexes exist
- Basic ORM create/query smoke tests pass

**Progress notes**
- 2026-04-03: Added SQLAlchemy engine/session foundations under `libs/data`, Alembic scaffolding, and an initial migration that enables the TimescaleDB extension on PostgreSQL. Full schema models, hypertable migration, and table/index coverage remain open.
- 2026-04-03: Validated the new DB foundation with migration upgrade/downgrade tests, session lifecycle tests, backend import smoke, and the full backend test suite. Milestone 2 remains in progress.
- 2026-04-03: Added ORM models for the Milestone 2 tables plus an explicit initial schema migration covering symbols, candles, jobs, datasets, training, model registry, MT5 account state, paper-trading records, and audit/system logs. Candle deduplication and approval threshold checks now exist at the DB layer.
- 2026-04-03: Validated schema creation through Alembic and ORM smoke tests on SQLite. PostgreSQL/Timescale-specific hypertable creation and real extension validation are still outstanding, so Milestone 2 is not complete yet.
- 2026-04-03: Added a dedicated hypertable migration for `ohlc_candles` plus a Docker-backed TimescaleDB validation path that can verify the extension, hypertable registration, index presence, and downgrade/re-upgrade behavior on PostgreSQL.
- 2026-04-03: Updated `ohlc_candles` to use the natural composite key `(symbol_id, timeframe, candle_time)` so TimescaleDB hypertable conversion satisfies partition-key uniqueness rules.
- 2026-04-03: Milestone 2 is complete. Validation passed on both SQLite and a real TimescaleDB/PostgreSQL container: schema upgrade on a fresh DB, downgrade-to-base and re-upgrade, hypertable inspection for `ohlc_candles`, index inspection, and ORM create/query smoke coverage.

---

### Milestone 3: API foundation, auth skeleton, and health endpoints
**Scope**
- Build FastAPI app structure
- Add API versioning and router layout
- Add health endpoints:
  - `/health`
  - `/health/db`
  - `/health/redis`
  - `/health/gpu`
- Add simple auth skeleton sufficient for MVP
- Add Pydantic schemas and error handling conventions
- Add dependency injection for DB/session/config
- Add system status summary endpoint

**Done when**
- API starts cleanly
- Health endpoints return useful status
- Router organization is established for future modules
- Auth/session scaffolding exists without blocking later work

**Validation**
- API starts locally
- Health endpoints respond successfully
- DB/Redis health checks behave correctly when dependencies are down
- OpenAPI schema builds without errors

**Progress notes**
- 2026-04-03: Added versioned API routing under `/api/v1`, centralized API dependency injection for settings/DB/Redis, root and health endpoints, a system status summary endpoint, and standardized validation/HTTP error response handlers.
- 2026-04-03: Validated the API foundation slice with backend smoke imports, health/status endpoint tests, degraded dependency behavior checks, and OpenAPI path generation. Auth/session scaffolding is still outstanding, so Milestone 3 remains in progress.
- 2026-04-03: Added the auth/session scaffold with reusable bearer-token dependencies, environment-aware auth safety rules, a versioned `/api/v1/auth/session` endpoint, and `.env`/README coverage for local versus token-protected API modes.
- 2026-04-03: Milestone 3 is complete. Validation passed for app bootstrap, OpenAPI generation, degraded health behavior, auth-disabled local session access, static-token auth enforcement, and full backend regression coverage.

---

### Milestone 4: Worker foundation, Celery queues, and job state tracking
**Scope**
- Configure Celery with Redis broker/backend
- Define queues:
  - ingestion
  - preprocessing
  - supervised_training
  - rl_training
  - evaluation
  - trading
  - maintenance
- Add task base classes, retry policy, logging, and status updates
- Create shared job state update utilities
- Add worker startup and scheduler startup modules
- Add status polling endpoints for jobs

**Done when**
- Worker can start and consume tasks
- Tasks can update DB-backed status fields
- Retries and failure logging are in place
- Queue separation exists

**Validation**
- Sample Celery task executes successfully
- Failure path writes error state and logs
- Retry path is observable
- API can read job state from DB

**Progress notes**
- 2026-04-03: Added explicit Celery queue definitions and routing for the worker foundation, plus a reusable tracked-task base that updates DB-backed job state on start, progress, retry, success, and failure.
- 2026-04-03: Added shared job lookup/state-update utilities and a versioned API polling endpoint at `/api/v1/jobs/{job_type}/{job_id}` so the API can read ingestion, preprocessing, and training job state from the database.
- 2026-04-03: Validated the worker foundation slice with queue configuration tests, tracked-task success/retry/failure tests against SQLite-backed job rows, API job polling tests, backend import validation, and the full backend test suite. Milestone 4 remained in progress because scheduler startup wiring was still outstanding.
- 2026-04-03: Added worker and scheduler runtime modules, Celery beat heartbeat scheduling, runtime queue/concurrency parsing, and CLI entry points that start the Celery worker and beat processes with explicit arguments instead of placeholder logging.
- 2026-04-03: Milestone 4 is complete. Validation passed for worker queue/runtime parsing, beat schedule registration, worker CLI startup, scheduler CLI startup, tracked task success/retry/failure handling, API job polling, backend import smoke, and the full backend regression suite.

---

### Milestone 5: Symbol validation and MT5 connectivity foundation
**Scope**
- Implement symbol validation service
- Primary validation path: MT5 symbol lookup
- Add provider abstraction interface for future fallback sources
- Implement MT5 connection service:
  - initialize terminal
  - fetch account info
  - list symbols
  - verify demo/live state
- Add endpoints:
  - validate symbol
  - get MT5 connection status
  - list available MT5 symbols
- Store validation results in DB

**Done when**
- User can submit a symbol and receive normalized validation response
- Invalid symbols are blocked
- MT5 connectivity state is queryable
- Demo/live distinction is available in backend

**Validation**
- Unit tests for symbol normalization and invalid symbol handling
- MT5 service mocked tests for account verification
- API validation endpoint tests
- Safety test: live account state is marked non-tradeable

**Progress notes**
- 2026-04-03: Added an MT5 provider abstraction in `libs/trading` with connection-state inspection, symbol listing, lazy `MetaTrader5` package loading, and fail-safe handling for missing credentials, missing package installs, initialization failures, and unavailable account metadata.
- 2026-04-03: Added authenticated MT5 API endpoints for connection status and symbol listing at `/api/v1/mt5/status` and `/api/v1/mt5/symbols`, including explicit live-account blocking semantics via `paper_trading_allowed=False` when the connected account is not identified as demo.
- 2026-04-03: Validated the MT5 connectivity slice with mocked gateway tests for demo/live account handling and package-unavailable cases, API endpoint tests for MT5 status and symbol listing, backend import validation, and the full backend regression suite. Milestone 5 remained in progress because symbol validation submission/storage and the validation endpoint were still outstanding.
- 2026-04-03: Added a normalized symbol validation flow with MT5 as the primary provider path, authenticated `/api/v1/symbols/validate` submission, invalid-format and symbol-not-found handling, exact/prefix MT5 symbol matching, and DB persistence for `symbols` plus `symbol_validation_results`.
- 2026-04-03: Milestone 5 is complete. Validation passed for symbol normalization, invalid symbol handling, MT5 demo/live safety behavior, MT5 connectivity endpoints, validation endpoint persistence, backend import smoke, and the full backend regression suite.

---

### Milestone 6: OHLC ingestion pipeline for 1m / 5m / 15m
**Scope**
- Build ingestion service for 1m, 5m, 15m candles
- Support:
  - initial backfill
  - incremental sync
  - retries
  - resumable jobs
  - UTC normalization
  - deduplication
- Add ingestion job tracking and progress fields
- Store provider/source metadata
- Add endpoints to:
  - request ingestion
  - inspect ingestion status
  - retry failed ingestion
- Automatically enqueue ingestion after symbol validation/training request

**Done when**
- Valid symbol can trigger OHLC data ingestion
- Candles are stored in DB without duplicates
- Job progress is visible
- Incremental sync uses last successful candle timestamp

**Validation**
- Ingestion inserts candles for all 3 timeframes
- Duplicate candle insert attempts do not create duplicates
- Failed ingestion can retry cleanly
- End-to-end test from training request to ingestion job creation passes

**Progress notes**
- 2026-04-03: Added an authenticated ingestion request endpoint at `/api/v1/ingestion/request` that creates `ingestion_jobs` rows for existing validated symbols, records requested timeframes/sync mode/lookback settings, and enqueues an ingestion worker task instead of doing ingestion inside the API process.
- 2026-04-03: Added MT5-backed candle fetch support plus a worker-side ingestion executor that resolves incremental start times from the last stored candle, normalizes fetched candle timestamps to UTC, persists OHLC candles with deduplication against existing composite keys, and updates ingestion job counters plus `last_successful_candle_time`.
- 2026-04-03: Validated the ingestion foundation slice with API request/enqueue tests, worker ingestion persistence tests covering multi-timeframe inserts and incremental start-time advancement, backend import validation, and the full backend regression suite. Milestone 6 remains in progress because retry endpoints, resumable replay handling, and broader end-to-end orchestration from upstream flows are still outstanding.
- 2026-04-03: Added an authenticated retry endpoint at `/api/v1/ingestion/{job_id}/retry` that only requeues failed ingestion jobs, clears stale failure/progress counters before dispatch, and records manual retry metadata without running ingestion work in the API process.
- 2026-04-03: Validated the retry slice with ingestion API tests for success, unknown-symbol rejection, failed-job retry, and non-failed retry rejection, plus backend import validation and the full backend regression suite. Milestone 6 remains in progress because resumable replay handling and upstream auto-enqueue orchestration are still outstanding.
- 2026-04-03: Added resumable ingestion checkpoints in the worker path so each timeframe records running/succeeded/failed state, failed attempts persist pending timeframe metadata, and retries can skip already-completed timeframes instead of replaying the whole job.
- 2026-04-03: Validated resumable ingestion with worker tests covering partial failure and retry-safe continuation from remaining timeframes, plus the ingestion API suite, backend import validation, and the full backend regression suite. Milestone 6 remains in progress because upstream auto-enqueue orchestration and its end-to-end validation are still outstanding.
- 2026-04-03: Added a minimal training-request intake endpoint at `/api/v1/training/request` that persists `training_requests` rows and automatically creates plus enqueues the prerequisite ingestion job instead of starting any long-running training work inside the API process.
- 2026-04-03: Added ingestion regression coverage for duplicate candle attempts and validated the upstream orchestration path from training request creation to ingestion job creation, including fail-safe enqueue handling.
- 2026-04-03: Milestone 6 is complete. Validation passed for 1m/5m/15m ingestion, deduplicated candle persistence, failed-job retry and resumable continuation, job status visibility, and end-to-end training-request-triggered ingestion job creation.

---

### Milestone 7: Feature engineering and dataset versioning
**Scope**
- Build preprocessing pipeline to transform OHLC into features
- Add deterministic candlestick pattern detection:
  - doji
  - hammer
  - hanging man
  - bullish engulfing
  - bearish engulfing
  - morning star
  - evening star
  - shooting star
  - pin bar
  - inside bar
  - outside bar
- Add indicators and structural features
- Add multi-timeframe alignment features
- Build label generation logic
- Create `feature_sets` and `dataset_versions`
- Add preprocessing tasks and endpoints

**Done when**
- Ingested candles can be transformed into versioned features/datasets
- Feature generation is deterministic
- Patterns are reusable in training and inference paths
- Preprocessing job state is visible

**Validation**
- Unit tests for candlestick pattern detection
- Unit tests for key feature calculations
- Leakage checks for label generation
- Preprocessing task integration test produces a dataset version

**Progress notes**
- 2026-04-03: Added a reusable `rl_trade_features.patterns` module with deterministic candlestick pattern detection for doji, hammer, hanging man, bullish/bearish engulfing, morning/evening star, shooting star, pin bar, inside bar, and outside bar.
- 2026-04-03: Validated the pattern core with focused unit tests for all listed candlestick patterns plus backend import validation and the full backend regression suite. Milestone 7 remains in progress because indicators, multi-timeframe features, label generation, dataset versioning, and preprocessing task orchestration are still outstanding.
- 2026-04-03: Added reusable indicator and structural feature primitives in `rl_trade_features` for SMA, EMA, RSI, true range, ATR, and normalized single-candle shape features so later preprocessing flows can compose deterministic feature columns without external dependencies.
- 2026-04-03: Validated the feature-calculation slice with focused unit tests for key indicator and structure calculations plus backend import validation and the full backend regression suite. Milestone 7 remains in progress because multi-timeframe alignment, label generation, dataset versioning, and preprocessing task orchestration are still outstanding.
- 2026-04-03: Added leakage-safe label generation helpers in `rl_trade_features.labels` for fixed-horizon forward returns and trade-setup direction labels, with explicit trailing-horizon null handling so labels only depend on the requested future window.
- 2026-04-03: Validated the label-generation slice with focused unit tests for buy/sell/no-trade outcomes and future-window leakage guards plus backend import validation and the full backend regression suite. Milestone 7 remains in progress because multi-timeframe alignment, dataset versioning, and preprocessing task orchestration are still outstanding.
- 2026-04-03: Added deterministic multi-timeframe alignment helpers in `rl_trade_features.alignment` so higher-timeframe feature points can be joined onto base-timestamp rows without leaking future values, with optional staleness cutoffs for dropping outdated context.
- 2026-04-03: Validated the alignment slice with focused unit tests for past-only joins, future-leak prevention, stale-value dropping, and UTC normalization plus backend import validation and the full backend regression suite. Milestone 7 remains in progress because dataset versioning and preprocessing task orchestration are still outstanding.
- 2026-04-03: Added deterministic dataset-versioning helpers in `rl_trade_features.datasets` for feature-set registration, stable dataset hashing/version tags, and idempotent persistence into `feature_sets` plus `dataset_versions`.
- 2026-04-03: Validated the dataset-versioning slice with focused tests for deterministic hashes, feature-set persistence, dataset-version metadata persistence, and idempotent version reuse plus backend import validation and the full backend regression suite. Milestone 7 remains in progress because preprocessing tasks, endpoints, and end-to-end dataset-production flow are still outstanding.
- 2026-04-03: Added a real worker-side preprocessing executor plus `jobs.run_preprocessing_job` Celery wiring so `preprocessing_jobs` can read ingested candles, compute deterministic features and labels, persist a `feature_set`, create a `dataset_version`, and attach the result back to the job.
- 2026-04-03: Validated the preprocessing-worker slice with focused worker tests for queue routing and end-to-end dataset creation from seeded 1m/5m/15m candles, plus backend import validation and the full backend regression suite. Milestone 7 remains in progress because preprocessing API endpoints and the request-to-job orchestration path are still outstanding.
- 2026-04-03: Added an authenticated preprocessing request endpoint at `/api/v1/preprocessing/request` that creates `preprocessing_jobs` rows and enqueues the preprocessing worker instead of doing dataset construction inside the API process.
- 2026-04-03: Validated the request-driven preprocessing flow with API tests that cover job creation/enqueue and end-to-end dataset production plus job-state visibility through `/api/v1/jobs/preprocessing/{job_id}`.
- 2026-04-03: Milestone 7 is complete. Validation passed for candlestick-pattern detection, indicator/structure calculations, leakage-safe labels, multi-timeframe alignment, deterministic dataset versioning, preprocessing worker execution, preprocessing API request orchestration, backend import smoke, and the full backend regression suite.

---

### Milestone 8: Supervised training pipeline
**Scope**
- Implement supervised model training using PyTorch
- Add at least one baseline model for comparison
- Support:
  - time-based split
  - walk-forward validation
  - saved feature schema
  - saved scalers
  - saved model artifacts
  - metrics persistence
- Model outputs:
  - buy / sell / no-trade
  - confidence score
  - projected setup quality
- Add training job endpoints and DB records

**Done when**
- Dataset version can trigger supervised training
- Training artifacts are saved and linked in DB
- Training metrics are visible
- GPU/CPU device used is recorded

**Validation**
- Training smoke test on sample dataset
- Artifact files saved and reloadable
- Metrics persisted to DB
- Failing training job is captured and recoverable

---

### Milestone 9: RL environment and RL training pipeline
**Scope**
- Implement custom Gymnasium trading environment
- Add PPO training via Stable-Baselines3
- Include:
  - candle window observation
  - engineered features
  - candlestick pattern features
  - multi-timeframe context
  - position state
- Reward design should account for:
  - RR >= 2
  - drawdown
  - overtrading
  - spread/slippage approximation
- Persist RL artifacts and metrics

**Done when**
- RL training can run against a dataset/environment
- PPO training job produces saved artifacts and metrics
- RL training is isolated from API runtime

**Validation**
- Environment reset/step tests pass
- PPO smoke train runs on small sample data
- Artifact persistence works
- RL training job status transitions correctly

---

### Milestone 10: Evaluation, approval gating, and model registry
**Scope**
- Build evaluation pipeline for supervised and RL models
- Compute metrics and persist evaluation reports
- Implement approval gating rules:
  - confidence >= 70%
  - risk-to-reward >= 2.0
  - sufficient sample size
  - acceptable drawdown
  - no critical data issue
- Create approved model registry and status lifecycle
- Add endpoints for listing models, evaluations, and approved symbols

**Done when**
- Trained models can be evaluated
- Approval/rejection is determined by backend logic
- Approved models are queryable
- Backend has a single reusable gate for “is symbol tradeable”

**Validation**
- Unit tests for approval gating logic
- Evaluation report persistence test
- Rejection path test for low confidence / low RR / high drawdown
- Approved symbol query test

---

### Milestone 11: Paper trading engine and backend enforcement
**Scope**
- Build paper trading service integrated with MT5 Demo account
- Add signal generation service gated by approved model status
- Add backend enforcement:
  - block unapproved symbols
  - block non-demo accounts
  - block trade if confidence < 70
  - block trade if RR < 2
- Implement order/position/history sync
- Add endpoints to:
  - start paper trading
  - stop paper trading
  - list signals
  - list orders
  - list positions
  - close position

**Done when**
- Only approved symbols can reach trade execution path
- Demo-only safety is enforced in backend
- Signals/orders/positions are persisted
- Paper trading state is visible in dashboard APIs

**Validation**
- Tests for backend trade gating
- MT5 demo safety check tests
- Signal-to-order flow integration test with mocks
- Manual dry-run smoke test path

---

### Milestone 12: WebSocket events and realtime progress updates
**Scope**
- Implement WebSocket event broadcasting for:
  - validation result
  - ingestion progress
  - preprocessing progress
  - training progress
  - evaluation status
  - approval status
  - signal events
  - position updates
  - equity updates
  - alerts
- Add backend event emitters from tasks/services
- Add reconnect-friendly event schema

**Done when**
- Major job states and trading events can stream to clients
- Frontend can subscribe to live state
- Event payloads are typed and consistent

**Validation**
- WebSocket connection smoke test
- Event schema tests
- Manual flow test: ingestion/training updates appear live

---

### Milestone 13: Frontend dashboard pages and workflows
**Scope**
- Build frontend pages:
  - login
  - overview dashboard
  - symbol management
  - ingestion
  - preprocessing
  - training
  - model registry
  - evaluation/backtest
  - paper trading
  - MT5 settings/status
  - logs
- Implement main UX flow:
  - enter symbol
  - validate
  - request training
  - watch ingestion
  - watch preprocessing
  - watch training
  - inspect model
  - see approval
  - start paper trading
- Add charts/tables/status badges

**Done when**
- Full main user flow is usable from UI
- Frontend consumes API + WebSocket updates
- Approved symbol state and job progress are visible

**Validation**
- Frontend typecheck/build passes
- Key page rendering smoke tests pass
- Manual walkthrough of primary UX works

---

### Milestone 14: Docker Compose, GPU wiring, and runtime validation
**Scope**
- Add Docker Compose services:
  - frontend
  - api
  - worker
  - scheduler
  - postgres
  - redis
- Configure TimescaleDB image/setup
- Configure training worker GPU access
- Add healthchecks, volumes, and startup dependencies
- Add startup checks for DB, Redis, MT5, and CUDA availability
- Add clear logs for missing GPU / dependency failures

**Done when**
- Full stack can be launched through Docker Compose
- Training worker can see GPU when available
- System degrades safely without GPU
- Services expose clear readiness state

**Validation**
- `docker compose config` passes
- Full stack boots locally
- DB and Redis healthchecks pass
- GPU detection logs are visible in training worker

---

### Milestone 15: Seed data, smoke tests, docs, and final hardening
**Scope**
- Add seed/demo records where helpful
- Add end-to-end smoke tests for critical path
- Expand README with setup and run instructions
- Document env vars
- Add troubleshooting notes
- Review logging, safety guards, and error handling
- Tighten tests for:
  - symbol validation
  - OHLC deduplication
  - pattern detection
  - feature generation
  - approval gating
  - MT5 demo safety
  - signal creation gating
  - API health endpoints

**Done when**
- Repo can be set up by another engineer
- Critical flows have automated coverage
- Docs are usable and accurate
- Safety guards are present and visible

**Validation**
- Test suite passes
- README setup followed from clean environment
- Core smoke path works:
  - validate symbol
  - ingest candles
  - preprocess
  - train
  - evaluate
  - approve
  - paper trade

---

## Risks / assumptions
- MT5 Python integration may depend on terminal availability and environment-specific setup
- Historical OHLC source may vary in reliability; provider abstraction is required
- RL training quality may be unstable; supervised model should remain the primary tradeability gate
- GPU may be unavailable in some environments; training must degrade safely
- Backtest realism is limited by spread/slippage assumptions and data quality
- Paper trading must never assume live-safe logic; demo-only enforcement is mandatory

---

## Non-negotiable backend gates
The backend must never execute a trade unless all of the following are true:
- symbol validated successfully
- OHLC data exists
- preprocessing complete
- trained model exists
- latest evaluation passed
- approved model exists
- confidence >= 0.70
- risk-to-reward >= 2.0
- MT5 account connected
- MT5 account verified as DEMO
- risk filters pass

---

## Validation commands
These commands are placeholders and should be updated to match the actual repo tooling as files are created.

### Backend
- run backend tests
- run backend lint
- run backend type checks
- start API app locally

### Worker
- run worker tests
- start Celery worker
- start scheduler
- run sample task

### Frontend
- install dependencies
- run frontend typecheck
- run frontend build
- run frontend tests

### Infra
- run Alembic migrations
- run Docker Compose config validation
- boot stack with Docker Compose

---

## Next step
Start with **Milestone 1: Monorepo scaffold and shared configuration**.

Immediate outputs expected from Codex:
1. architecture summary
2. folder tree
3. initial repo files
4. backend/frontend/worker bootstrap
5. shared config and logging
6. `.env.example`
7. root README
