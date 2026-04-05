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
- [x] Milestone 8: Supervised training pipeline
- [x] Milestone 9: RL environment and RL training pipeline
- [x] Milestone 10: Evaluation, approval gating, and model registry
- [x] Milestone 11: Paper trading engine and backend enforcement
- [x] Milestone 12: WebSocket events and realtime progress updates
- [x] Milestone 13: Frontend dashboard pages and workflows
- [x] Milestone 14: Docker Compose, GPU wiring, and runtime validation
- [x] Milestone 15: Seed data, smoke tests, docs, and final hardening

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

**Progress notes**
- 2026-04-03: Added a supervised-training intake path at `/api/v1/training/supervised/request` that accepts a ready `dataset_version`, creates linked `training_requests` plus `supervised_training_jobs` rows, and enqueues the supervised-training worker instead of running training in the API process.
- 2026-04-03: Added supervised-training worker routing plus a first real baseline-training executor that rebuilds the deterministic dataset from candles, performs time-based split and walk-forward comparison across baseline classifiers, saves feature schema/scaler/model/metrics artifacts, and persists `supervised_models`, `model_artifacts`, and job metrics with recorded CPU device usage.
- 2026-04-03: Validated the supervised-training foundation slice with focused API request tests, worker success/failure tests, job-polling metric visibility coverage, backend import validation, and the full backend regression suite. Milestone 8 remains in progress because PyTorch-based model training, richer model outputs, and broader training-job API surfaces are still outstanding.
- 2026-04-03: Added reloadable supervised artifact helpers in `libs/ml` plus a dedicated `/api/v1/training/supervised/{job_id}` status endpoint that exposes linked model metadata, artifact inventory, and persisted training metrics for supervised jobs.
- 2026-04-03: Validated supervised artifact reload and dedicated training-status coverage with focused ML/API tests, backend import validation, and the full backend regression suite. Milestone 8 remains in progress because the actual PyTorch training path is still not implemented in the current environment.
- 2026-04-03: Added a supervised training retry endpoint at `/api/v1/training/supervised/{job_id}/retry` that only requeues failed jobs, resets stale supervised job state, synchronizes the linked training request back to `pending`, and removes any partial supervised model/artifact rows before re-enqueueing.
- 2026-04-03: Hardened shared job-state helpers so tracked jobs without a `details` column, including supervised training jobs, can still use the generic progress/requeue lifecycle safely.
- 2026-04-03: Validated supervised retry/recoverability with focused API tests for successful requeue and conflict rejection, backend import validation, and the full backend regression suite. Milestone 8 remains in progress because the actual PyTorch training path is still not implemented in the current environment.
- 2026-04-03: Added the real PyTorch supervised training path with a small MLP classifier, deterministic CPU-safe device selection, persisted torch checkpoint artifacts, configurable supervised hyperparameters, and training smoke coverage on a sample dataset while preserving the existing baseline comparison path.
- 2026-04-03: Milestone 8 is complete. Validation passed for dataset-version-triggered supervised training requests, PyTorch smoke training, time-based split plus walk-forward validation, artifact persistence and reload, metrics visibility through job and training-status APIs, failed-job retry/recovery, backend import validation, and the full backend regression suite.

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

**Progress notes**
- 2026-04-03: Added a custom `ForexTradingEnv` Gymnasium environment in `libs/ml` built around the existing deterministic dataset contract, with windowed feature observations, position state, UTC-safe step progression, and reward components for spread/slippage approximation, overtrading, drawdown, and risk-to-reward bonus handling.
- 2026-04-03: Validated the RL environment slice with focused reset/step tests covering profitable long steps, reversal penalties, drawdown penalties, and required feature validation, plus backend import validation and the full backend regression suite. PPO training, RL artifact persistence, and RL job orchestration remain outstanding, so Milestone 9 stays in progress.
- 2026-04-03: Added Stable-Baselines3 PPO helpers in `libs/ml` that train against the custom trading environment, evaluate a deterministic episode, and persist reloadable RL artifacts as JSON metadata plus a saved PPO checkpoint.
- 2026-04-03: Validated the PPO slice with a small-sample smoke training run, RL artifact save/load coverage, backend import validation, and the full backend regression suite. RL job orchestration and DB-backed RL status transitions are still outstanding, so Milestone 9 remains in progress.
- 2026-04-03: Added the worker-side RL training execution path with Celery routing on the `rl_training` queue, DB-backed `rl_training_jobs` lifecycle updates, persisted `rl_models` plus `model_artifacts`, and generic job-status visibility for RL metrics through the existing jobs endpoint.
- 2026-04-03: Milestone 9 is complete. Validation passed for environment reset/step behavior, PPO smoke training, RL artifact save/load, RL worker success/failure transitions, generic RL job polling, backend import validation, and the full backend regression suite.

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

**Progress notes**
- 2026-04-03: Added a shared backend approval gate in `libs/trading` that evaluates confidence, risk-to-reward, sample size, drawdown, and critical-data checks, plus a reusable `is_symbol_tradeable` helper for later trading enforcement.
- 2026-04-03: Added API-side evaluation persistence and approval handling with `/api/v1/evaluations` and `/api/v1/evaluations/approved-symbols`, including `model_evaluations` writes, `approved_models` activation/revocation, model status updates, and audit-log entries for approval decisions.
- 2026-04-03: Validated the evaluation slice with direct approval-gate unit tests, evaluation persistence coverage, rejection-path coverage for low confidence / low RR / high drawdown / critical data issues, approved-symbol query coverage, backend import validation, and the full backend regression suite. Milestone 10 remains in progress because broader model/evaluation listing surfaces and final registry lifecycle coverage are still outstanding.
- 2026-04-04: Added read-only model registry listing APIs at `/api/v1/evaluations/models` and `/api/v1/evaluations/reports`, with filters for symbol, model type, and model status where applicable, so supervised and RL model records plus persisted evaluation reports are queryable from a single backend surface.
- 2026-04-04: Validated the new listing slice with approval-gate unit tests, route/schema compile checks, direct service-level SQLite validation for approved/rejected evaluation persistence plus model/report listing behavior, and focused router import checks. Milestone 10 remains in progress because final approved-model registry lifecycle coverage is still outstanding.
- 2026-04-04: Switched the evaluation API tests to a route-scoped FastAPI test app so Milestone 10 validation no longer depends on unrelated worker/ML imports, and added approved-model registry lifecycle coverage for model replacement and approval revocation on rejection.
- 2026-04-04: Milestone 10 is complete. Validation passed for approval-gate unit logic, evaluation report persistence, rejection paths, approved-symbol queries, model and evaluation listing APIs, approval replacement/revocation lifecycle behavior, and the focused Milestone 10 API test suite.

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

**Progress notes**
- 2026-04-04: Added a reusable backend paper-trade gate in `libs/trading` that centralizes Milestone 11 enforcement for approved-model lookup, MT5 demo-only safety, and minimum confidence/risk-to-reward checks before any symbol can reach the paper-trade execution path.
- 2026-04-04: Validated the backend-gating foundation with focused tests covering approved-symbol allow, unapproved-symbol rejection, live-account blocking, low-confidence / low-risk-reward rejection, existing approval-gate unit coverage, and MT5 gateway demo/live safety behavior. Milestone 11 remains in progress because signal generation, order/position persistence flows, sync logic, and trading endpoints are still outstanding.
- 2026-04-04: Added a paper-trade signal API slice with gated signal creation and signal listing at `/api/v1/trading/signals`, including backend approval/demo-only enforcement, persisted accepted signals, blocked-attempt audit logging, and signal visibility filters by symbol/status.
- 2026-04-04: Validated the signal slice with focused trading API tests for accepted signal persistence, unapproved-symbol rejection, live-account blocking, signal listing visibility, plus the existing paper-trade gate, approval-gate, and MT5 gateway safety suites. Milestone 11 remains in progress because order/position persistence, execution flow, sync logic, and the remaining trading endpoints are still outstanding.
- 2026-04-04: Added the signal-to-order execution slice with `/api/v1/trading/orders` and `/api/v1/trading/positions`, mocked MT5 order submission support in the gateway, backend re-checks at execution time, persisted order records, automatic open-position plus trade-execution persistence on filled market orders, and read-only order/position listing filters.
- 2026-04-04: Validated the execution slice with focused trading API tests for accepted signal-to-order flow, broker rejection handling, order/position listing visibility, paper-trade gate coverage, approval-gate coverage, and MT5 gateway order-submission plus demo/live safety tests. Milestone 11 remains in progress because start/stop controls, close-position behavior, order/position/history sync, and a manual dry-run path are still outstanding.
- 2026-04-04: Added close-position behavior at `/api/v1/trading/positions/{position_id}/close`, including backend re-checks before close submission, persisted closing-order records, realized PnL calculation on filled closes, close trade-execution persistence, and rejection handling that leaves the original position open when the broker rejects the close.
- 2026-04-04: Validated the close-position slice with focused trading API tests for successful close persistence, broker-rejected closes, order/position listing visibility, paper-trade gate coverage, approval-gate coverage, and MT5 gateway submission safety tests. Milestone 11 remains in progress because start/stop controls, order/position/history sync, and a manual dry-run path are still outstanding.
- 2026-04-04: Added runtime paper-trading controls at `/api/v1/trading/status`, `/api/v1/trading/start`, and `/api/v1/trading/stop`, including demo-only backend checks before enablement, persisted runtime state on the MT5 account record, dashboard-visible aggregate counts for approved symbols and accepted/open trading records, and audit logging for runtime state changes.
- 2026-04-04: Validated the runtime-control slice with focused trading API tests for start-state persistence, live-account blocking, stop-state persistence, plus the existing signal/order/position flow, paper-trade gate coverage, approval-gate coverage, and MT5 gateway safety tests. Milestone 11 remains in progress because order/position/history sync and a manual dry-run smoke path are still outstanding.
- 2026-04-04: Added explicit MT5 sync at `/api/v1/trading/sync`, including demo-only backend gating before broker reads, order-history reconciliation for submitted orders, open-position reconciliation for unrealized PnL updates, close-history reconciliation for submitted close orders, trade-execution creation, persisted runtime last-sync metadata, and sync audit logging.
- 2026-04-04: Validated the sync slice with focused trading API tests for submitted-order fill sync, open-position metric refresh, close-position reconciliation from broker history, plus MT5 gateway history/position parsing coverage and the existing paper-trade gate and approval-gate safety suites. Milestone 11 remains in progress because the manual dry-run smoke path is still outstanding.
- 2026-04-04: Added a manual paper-trading dry-run smoke path at `python -m rl_trade_api.tools.paper_trading_dry_run`, backed by a temporary SQLite database, a route-scoped FastAPI app, and a demo-only fake MT5 gateway so operators can exercise the full paper-trading workflow without touching real broker infrastructure.
- 2026-04-04: Validated the manual dry-run path by running the command directly and adding dedicated smoke coverage for start, signal creation, submitted order flow, MT5 sync reconciliation, close reconciliation, and stop. Milestone 11 is complete: approved-symbol gating, demo-only backend enforcement, signal/order/position persistence, dashboard-visible trading state, sync logic, and the required validation path are all satisfied.

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

**Progress notes**
- 2026-04-04: Added the Milestone 12 WebSocket foundation with typed live-event schemas, an in-process event broadcaster with replay cursor support, and a `/ws/events` endpoint that streams live or replayed events with optional topic filtering.
- 2026-04-04: Validated the WebSocket foundation slice with a route-scoped connection smoke test for live delivery, replay-cursor coverage, static-token WebSocket auth coverage, and event schema/replay tests. Milestone 12 remains in progress because backend emitters and the manual live-update flow are still outstanding.
- 2026-04-04: Added the first backend emitter slice for Milestone 12 by publishing `training_progress` events from the supervised training request and retry services, including live payloads for pending job creation and manual retry requeue events.
- 2026-04-04: Validated the supervised training emitter slice with route-scoped WebSocket tests that open `/ws/events`, trigger supervised training request and retry flows, and assert that live `training_progress` messages are delivered with typed payloads. Milestone 12 remains in progress because worker-driven emitters for long-running progress and the manual live-update flow are still outstanding.
- 2026-04-04: Added API-side `ingestion_progress` and `preprocessing_progress` emitters for ingestion request, ingestion retry, and preprocessing request flows, with typed live payloads covering pending job creation and manual retry requeue state.
- 2026-04-04: Validated the pipeline emitter slice with route-scoped WebSocket tests that open `/ws/events`, trigger ingestion and preprocessing API flows, and assert that live pipeline-progress messages are delivered with typed payloads alongside the existing training-event coverage. Milestone 12 remains in progress because worker-driven long-running progress emitters and the manual live-update flow are still outstanding.
- 2026-04-04: Added API-side `evaluation_status` and `approval_status` emitters for model evaluation creation so backend approval decisions now publish typed live events for both evaluation outcomes and approval-state changes.
- 2026-04-04: Validated the evaluation emitter slice with route-scoped WebSocket tests that open `/ws/events`, trigger approved and rejected evaluation flows, and assert that live evaluation/approval messages are delivered with typed payloads alongside the existing training and pipeline event coverage. Milestone 12 remains in progress because worker-driven long-running progress emitters, trading/equity/alert emitters, and the manual live-update flow are still outstanding.
- 2026-04-04: Added API-side `signal_event` and `position_update` emitters for paper-trading signal acceptance, order submission with immediate fills, and successful close-position flows so trading lifecycle state now publishes typed live events from the backend services.
- 2026-04-04: Validated the trading emitter slice with route-scoped WebSocket tests that open `/ws/events`, trigger signal creation, order submission, and position close flows, and assert that live `signal_event` and `position_update` messages are delivered alongside the existing trading and Milestone 12 event coverage. Milestone 12 remains in progress because worker-driven long-running progress emitters, sync/equity/alert emitters, and the manual live-update flow are still outstanding.
- 2026-04-04: Added sync-side trading emitters so `/api/v1/trading/sync` now publishes `position_update` for reconciled position changes and persists `equity_snapshots` plus live `equity_update` events when MT5 account metrics are available from the backend connection state.
- 2026-04-04: Validated the sync/equity emitter slice with route-scoped WebSocket tests for sync-driven position and equity delivery, trading API assertions for persisted equity snapshots, and MT5 gateway coverage for balance/equity/margin fields in the demo connection state. Milestone 12 remains in progress because worker-driven long-running progress emitters, alert emitters, and the manual live-update flow are still outstanding.
- 2026-04-04: Added backend `alert` emitters for paper-trading safety blocks so blocked signal submission, blocked runtime start, blocked sync, and other trading guard failures can publish typed live warning events after the corresponding audit records are committed.
- 2026-04-04: Validated the alert slice with route-scoped WebSocket tests that open `/ws/events`, trigger blocked trading flows, and assert that live `alert` messages are delivered alongside the existing trading, equity, evaluation, pipeline, training, and WebSocket event coverage. Milestone 12 remains in progress because worker-driven long-running progress emitters and the manual live-update flow are still outstanding.
- 2026-04-04: Added worker-side long-running progress emitters in the tracked Celery task base so ingestion, preprocessing, supervised training, and RL training jobs can publish typed `ingestion_progress`, `preprocessing_progress`, and `training_progress` messages whenever task state changes or progress callbacks update persisted job rows.
- 2026-04-04: Added route-scoped WebSocket coverage for worker-driven ingestion, preprocessing, and supervised-training events by wiring eager Celery tasks to the shared event broadcaster during tests. Static validation passed for the changed Python files via `python3 -m py_compile`, but full `pytest` execution remains blocked in this environment because Python dev dependencies are not installed and outbound package installation is unavailable. Milestone 12 remains in progress because the manual live-update flow is still outstanding and the new worker-event slice still needs full runtime test validation in a provisioned dev environment.
- 2026-04-04: Added a dedicated manual live-update smoke tool at `rl_trade_api.tools.websocket_event_dry_run` plus smoke coverage so Milestone 12 now has a runnable path that opens `/ws/events`, executes eager ingestion and supervised-training jobs, and prints the live status sequence for both event streams from the shared WebSocket broadcaster.
- 2026-04-04: Updated the README with the manual WebSocket dry-run command and validated the new tool/test files with `python3 -m py_compile` plus `git diff --check`. Milestone 12 remains in progress because this environment still cannot execute the full runtime smoke path or pytest suite without the missing Python dependencies, so the final runtime validation requirement is not yet satisfied.
- 2026-04-04: Provisioned the repo-local `.venv`, fixed SQLite fixture/runtime issues in the new manual smoke path and worker-event tests, and validated Milestone 12 with `.venv/bin/python -m pytest tests/smoke/test_websocket_event_dry_run.py tests/api/test_pipeline_events.py tests/api/test_training_events.py tests/api/test_websocket_events.py -q` (`12 passed in 32.39s`) plus `PYTHONPATH=apps/api/src:apps/worker/src:libs/common/src:libs/data/src:libs/features/src:libs/ml/src:libs/trading/src .venv/bin/python -m rl_trade_api.tools.websocket_event_dry_run`, which completed successfully with live ingestion and supervised-training status streams. Milestone 12 is complete.

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
- Add Playwright end-to-end test setup
- Add reusable Playwright fixtures for auth, seeded demo state, and API mocking where needed
- Add browser coverage for Chromium first, with optional expansion later

**Done when**
- Full main user flow is usable from UI
- Frontend consumes API + WebSocket updates
- Approved symbol state and job progress are visible
- Core UI flows have Playwright coverage for happy-path behavior

**Validation**
- Frontend typecheck/build passes
- Key page rendering smoke tests pass
- Playwright happy-path tests pass for:
  - login
  - symbol validation
  - training request submission
  - job progress visibility
  - approved model visibility
  - paper trading start/stop flow
- Manual walkthrough of primary UX works

**Progress notes**
- 2026-04-04: Replaced the placeholder frontend hero with a Milestone 13 operator workspace foundation: a demo access gate plus an overview-first dashboard shell that surfaces backend-aligned symbol approval state, worker/job progress, MT5 demo status, paper-trading readiness, and the Milestone 12 live event rail.
- 2026-04-04: Added typed frontend demo-state modules for workflow stages, queue health, alerts, symbol approval snapshots, positions, and MT5 status so the UI foundation stays maintainable while the later milestone slices wire real API and WebSocket data.
- 2026-04-04: Validated the current UI foundation slice with `npm install`, `npm run frontend:build`, and `git diff --check`. Milestone 13 remains in progress because the rest of the pages, real API/WebSocket integration, and Playwright coverage are still outstanding.
- 2026-04-04: Wired the frontend login form to the real `/api/v1/auth/session` endpoint, added a small typed API client for `/api/v1/system/status`, `/api/v1/mt5/status`, `/api/v1/symbols/validate`, and `/api/v1/training/request`, and turned the symbol desk into a real operator console for validation-first training requests.
- 2026-04-04: Connected the overview workspace to `/ws/events` so ingestion, preprocessing, training, approval, and alert messages now update the live event rail and pipeline queue area from backend WebSocket traffic instead of only static placeholder data.
- 2026-04-04: Re-validated the frontend slice with `npm run frontend:build` and `git diff --check`. Milestone 13 remains in progress because more pages, broader real-data coverage, Playwright happy paths, and a full manual walkthrough are still outstanding.
- 2026-04-04: Extended the frontend API client and overview workspace to consume real approved-symbol, model-registry, evaluation-report, trading-status, signal, and position endpoints so the downstream operator flow now exposes model approval state and paper-trading readiness from backend data.
- 2026-04-04: Added backend-driven paper-trading controls in the UI for start, stop, and sync, plus runtime counters, approved-model tables, registry summaries, honest empty states, and WebSocket-triggered refreshes for approval and trading events.
- 2026-04-04: Re-validated this slice with `npm run frontend:build` and `git diff --check`. Milestone 13 remains in progress because dedicated pages, broader CRUD flows, Playwright coverage, and the full manual walkthrough are still outstanding.
- 2026-04-04: Refactored the frontend into smaller feature folders under `apps/frontend/src/features`, splitting the oversized root component into focused auth and workspace components plus section-level panels and extracted workspace view-model helpers.
- 2026-04-04: Kept the Milestone 13 behavior intact while making the frontend structure easier to extend for the remaining pages and flows, so later symbol-management, registry, evaluation, and trading slices can land without adding more cram to a single file.
- 2026-04-04: Re-validated the component-splitting slice with `npm run frontend:build` and `git diff --check`. Milestone 13 remains in progress because the remaining UI pages, Playwright coverage, and manual walkthrough are still outstanding.
- 2026-04-04: Added a lightweight workspace page shell with dedicated frontend views for overview, symbols, models, paper trading, and system status/logs, using hash-based navigation instead of keeping every operator surface on one long page.
- 2026-04-04: Reused the extracted section components inside page-level views so Milestone 13 now has clearer page coverage for symbol management, model registry, paper trading, and MT5/log surfaces without adding routing dependencies or fake placeholder screens.
- 2026-04-04: Re-validated the page-shell slice with `npm run frontend:build` and `git diff --check`. Milestone 13 remains in progress because the remaining page depth, Playwright happy-path coverage, and the full manual walkthrough are still outstanding.
- 2026-04-04: Added a frontend smoke-test stack with Vitest, jsdom, and React Testing Library so Milestone 13 now has key page rendering checks for the login screen plus the overview, models, and system workspace views.
- 2026-04-04: Added workspace smoke coverage that verifies authentication opens the operator shell and that hash-based navigation selects the expected page-level views without relying on placeholder-only rendering.
- 2026-04-04: Re-validated this slice with `npm run test --workspace @rl-trade/frontend`, `npm run frontend:build`, and `git diff --check`. Milestone 13 remains in progress because Playwright happy-path coverage and the required manual walkthrough are still outstanding.
- 2026-04-04: Added Playwright end-to-end scaffolding for the frontend with a Chromium-only config, a reusable mocked operator-workspace fixture, and a browser happy-path spec that covers login, symbol validation, training submission, queue progress updates, approved-model visibility, and paper-trading start/stop behavior without needing a live backend.
- 2026-04-04: Re-validated this slice with `npm run test --workspace @rl-trade/frontend`, `npm run test:e2e --workspace @rl-trade/frontend`, `npm run frontend:build`, and `git diff --check`. Milestone 13 remains in progress because the required manual walkthrough is still outstanding.
- 2026-04-04: Added a dedicated pipeline workspace view so ingestion, preprocessing, training progress, and live operator-facing event logs are first-class pages instead of staying buried inside the overview screen.
- 2026-04-04: Reused the existing queue, runway, and live-event sections inside the new pipeline page and extended smoke plus Playwright coverage so the main browser flow now proves cross-page movement from symbol intake into the downstream watch desk.
- 2026-04-04: Re-validated this slice with `npm run test --workspace @rl-trade/frontend`, `npm run test:e2e --workspace @rl-trade/frontend`, `npm run frontend:build`, and `git diff --check`. Milestone 13 remains in progress because the required manual walkthrough is still outstanding.
- 2026-04-04: Added a stage-level pipeline lens to the dedicated watch desk so ingestion, preprocessing, and training each show explicit status, progress, and latest operator-facing detail instead of relying only on the raw queue list and event rail.
- 2026-04-04: Reused the existing queue plus live-event view-models to derive the new stage summaries, keeping the pipeline page additive and maintainable without changing the underlying backend-driven workflow.
- 2026-04-04: Re-validated this slice with `npm run test --workspace @rl-trade/frontend`, `npm run test:e2e --workspace @rl-trade/frontend`, `npm run frontend:build`, and `git diff --check`. Milestone 13 remained in progress because the required manual walkthrough was still outstanding.
- 2026-04-04: Added an opt-in local manual walkthrough mode for the frontend so the primary UX can be exercised in a real browser without depending on a live backend stack, including local API/WebSocket mocking for validation, training submission, downstream progress, approval visibility, and paper-trading controls.
- 2026-04-04: Fixed the browser issues surfaced during the walkthrough validation by adding a lightweight favicon and proper login-form autocomplete hints, keeping the browser console clean during the operator flow.
- 2026-04-04: Manual walkthrough completed successfully in a real browser against `http://127.0.0.1:4174/?manualWalkthrough=1`, covering login, symbol validation, training submission, ingestion/preprocessing/training progress visibility, approved model inspection, and paper-trading start/stop with zero console errors. Milestone 13 is complete.

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

**Progress notes**
- 2026-04-04: Added the first Milestone 14 Compose slice with a root `compose.yaml`, a shared Python service image, a frontend image, `postgres`/`redis` infrastructure services, and `migrate`/`api`/`worker`/`scheduler` runtime services wired with volumes plus startup dependencies.
- 2026-04-04: Added container startup checks that log DB, Redis, MT5, and CUDA readiness before Python services start, so the stack reports dependency state explicitly and can degrade safely when MT5 or CUDA are unavailable.
- 2026-04-04: Added a `docker compose config` validation target plus Docker docs and optional Compose env defaults in `.env.example` so the new runtime wiring is discoverable and repeatable.
- 2026-04-04: Re-validated this slice with `python3 -m py_compile docker/scripts/startup_checks.py`, `docker compose config`, `git diff --check`, and a live Redis Compose startup that reached a healthy state. Milestone 14 remains in progress because the full stack has not been booted yet, GPU exposure has not been wired/validated yet, and TimescaleDB local boot is currently blocked here by a host `5432` port conflict.
- 2026-04-04: Split Compose host-published port overrides away from the app runtime port settings, added explicit `compose-build` and `compose-up` targets, and documented the alternate host-port path so local validation no longer depends on freeing `5432`/`6379`/`8000`/`4173`.
- 2026-04-04: Switched the Compose runtime to prebuilt shared images (`rl-trade-python:local` and `rl-trade-frontend:latest`) after live validation showed `docker compose up --build` was unpacking duplicate 3GB Python images and exhausting Docker Desktop disk space.
- 2026-04-04: Fixed the worker and scheduler Celery CLI bootstrap to pass subcommands directly to `celery_app.start(...)` instead of incorrectly prefixing `celery`, which was causing both services to crash-loop under Compose with `No such command 'celery'`.
- 2026-04-04: Re-validated Milestone 14 with `docker compose config`, `python3 -m py_compile docker/scripts/startup_checks.py`, targeted runtime tests (`tests/worker/test_runtime.py` and `tests/smoke/test_bootstrap.py`), `make compose-build`, and a real high-port Compose boot at `POSTGRES_HOST_PORT=55432`, `REDIS_HOST_PORT=56379`, `API_HOST_PORT=58000`, and `FRONTEND_HOST_PORT=54173`. `postgres`, `redis`, `api`, and `frontend` all reached healthy status, `migrate` exited `0`, and the worker logged the expected degraded CUDA message while staying up. Milestone 14 remains in progress because the positive GPU-available path has still not been validated in this environment.
- 2026-04-04: Split the default Compose worker topology into a CPU worker (`ingestion`, `preprocessing`, `evaluation`, `trading`, `maintenance`) plus a dedicated `training_worker` (`supervised_training`, `rl_training`) so training queues can be isolated from the rest of the runtime.
- 2026-04-04: Added `docker/compose.gpu.yaml` plus matching env vars and Make targets so GPU-capable hosts can request `gpus: all` only for `training_worker`, while the base stack remains runnable on non-GPU machines.
- 2026-04-04: Tightened startup-check service names so only `training_worker` reports CUDA readiness by default; the CPU worker now reports DB/Redis/MT5 readiness without misleading CUDA degradation logs.
- 2026-04-04: Re-validated the isolated-worker slice with `docker compose config`, `docker compose -f compose.yaml -f docker/compose.gpu.yaml config`, `python3 -m py_compile docker/scripts/startup_checks.py`, `make compose-build`, and another high-port local Compose boot. `worker` and `training_worker` both stayed up with separate queue ownership, `training_worker` logged the safe CPU fallback when no GPU was available, and the rest of the stack still reached healthy readiness states. Milestone 14 remains in progress because the positive GPU-available path still needs validation on a GPU-capable host.
- 2026-04-04: Added automated smoke coverage for the Docker runtime topology and startup-check routing. The new tests assert that base Compose isolates CPU queues from training queues, the GPU override targets only `training_worker`, and only `training_worker` performs CUDA readiness checks by default.
- 2026-04-04: Re-validated this test slice with `pytest tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py -q`, `python3 -m py_compile` on the new smoke tests, and `git diff --check`. Milestone 14 remains in progress because the actual GPU-available runtime path still has not been validated on a GPU-capable host.
- 2026-04-04: Hardened `docker/scripts/startup_checks.py` so it can run from the repo checkout without a preinstalled package path, and expanded CUDA reporting to include `NVIDIA_VISIBLE_DEVICES` plus detected device names when GPUs are available.
- 2026-04-04: Re-validated the startup-check slice with `pytest tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py -q`, `python3 -m py_compile docker/scripts/startup_checks.py tests/smoke/test_startup_checks.py`, and `git diff --check`. Milestone 14 remains in progress because this environment still cannot perform the final live `training_worker` GPU-available runtime boot on a GPU-capable host.
- 2026-04-04: Added a dedicated `docker/scripts/verify_training_worker_gpu.py` helper plus a `make validate-compose-gpu-runtime` target so the last Milestone 14 GPU-host check can assert the live `training_worker` logs reached the positive CUDA-ready path instead of relying on manual inspection.
- 2026-04-04: Re-validated the GPU-runtime verification slice with `pytest tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py tests/smoke/test_verify_training_worker_gpu.py -q`, `python3 -m py_compile docker/scripts/startup_checks.py docker/scripts/verify_training_worker_gpu.py tests/smoke/test_startup_checks.py tests/smoke/test_verify_training_worker_gpu.py`, and `git diff --check`. Milestone 14 remains in progress because the final live `make compose-up-gpu` plus `make validate-compose-gpu-runtime` run still requires a GPU-capable Docker host.
- 2026-04-04: Added a dedicated `docker/scripts/verify_compose_runtime.py` helper plus a `make validate-compose-runtime` target so the full Milestone 14 stack boot can be validated from `docker compose ps --format json` instead of relying on manual service-state inspection.
- 2026-04-04: Re-validated the Compose-runtime verification slice with `pytest tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_verify_compose_runtime.py -q`, `python3 -m py_compile docker/scripts/startup_checks.py docker/scripts/verify_training_worker_gpu.py docker/scripts/verify_compose_runtime.py tests/smoke/test_startup_checks.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_verify_compose_runtime.py`, and `git diff --check`. Milestone 14 remains in progress because the final live GPU-capable `training_worker` boot plus `make validate-compose-gpu-runtime` still requires hardware this environment does not provide.
- 2026-04-04: Hardened the Compose runtime validators to retry through transient startup states. `make validate-compose-runtime` now waits for services to move from `starting` to their target ready states, and `make validate-compose-gpu-runtime` now waits for the `training_worker` to emit its CUDA readiness line before deciding pass/fail.
- 2026-04-04: Re-validated the retry-capable runtime-validation slice with `pytest tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_verify_compose_runtime.py -q`, `python3 -m py_compile docker/scripts/startup_checks.py docker/scripts/verify_training_worker_gpu.py docker/scripts/verify_compose_runtime.py tests/smoke/test_startup_checks.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_verify_compose_runtime.py`, and `git diff --check`. Milestone 14 remains in progress because the final live GPU-capable `training_worker` boot plus `make validate-compose-gpu-runtime` still requires hardware this environment does not provide.
- 2026-04-04: Ran a real high-port local Compose boot again with the new runtime verifier at `POSTGRES_HOST_PORT=55432`, `REDIS_HOST_PORT=56379`, `API_HOST_PORT=58000`, and `FRONTEND_HOST_PORT=54173`. Live validation surfaced a real issue: `docker compose ps --format json` omitted the exited `migrate` container, so `make validate-compose-runtime` could not pass against the actual stack.
- 2026-04-04: Fixed `docker/scripts/verify_compose_runtime.py` to inspect `docker compose ps --all --format json`, then re-ran `make validate-compose-runtime` successfully against the live stack. Validation passed with `postgres=running+healthy`, `redis=running+healthy`, `migrate=exited(0)`, `api=running+healthy`, `worker=running`, `training_worker=running`, `scheduler=running`, and `frontend=running+healthy`.
- 2026-04-04: Re-validated this live-runtime slice with `pytest tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_verify_compose_runtime.py -q`, `python3 -m py_compile docker/scripts/startup_checks.py docker/scripts/verify_training_worker_gpu.py docker/scripts/verify_compose_runtime.py tests/smoke/test_startup_checks.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_verify_compose_runtime.py`, a real `make compose-build`, a real high-port `docker compose up -d`, a live `make validate-compose-runtime`, and `docker compose down --remove-orphans`. Milestone 14 remains in progress because the final live GPU-capable `training_worker` boot plus `make validate-compose-gpu-runtime` still requires hardware this environment does not provide.
- 2026-04-04: Reworked the Docker build caching path so dependency downloads are no longer tied to every source-code change. `docker/python.Dockerfile` now installs runtime dependencies from `pyproject.toml` before copying the full repo source, uses BuildKit pip cache mounts, and installs the local package afterward with `--no-deps`; `docker/frontend.Dockerfile` now uses an npm cache mount plus `npm ci`, and `make compose-build` now forces `DOCKER_BUILDKIT=1`.
- 2026-04-04: Added smoke coverage that locks in the new cache-layer behavior for the Python Dockerfile, frontend Dockerfile, and `compose-build` target so the repo keeps the cache-friendly build shape.
- 2026-04-04: Re-validated the Docker cache-layer slice with `pytest tests/smoke/test_docker_build_cache.py tests/smoke/test_verify_compose_runtime.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py -q`, `git diff --check`, a full `make compose-build`, and an immediate second `make compose-build` that reused cached layers for both the heavy Python dependency install and the frontend dependency/build steps. Milestone 14 remains in progress because the final live GPU-capable `training_worker` boot plus `make validate-compose-gpu-runtime` still requires hardware this environment does not provide.
- 2026-04-04: Added a dedicated `docker/scripts/verify_gpu_host.py` helper plus a `make validate-compose-gpu-host` target so GPU override attempts can fail fast when the Docker engine is not configured with an `nvidia` runtime, instead of discovering that only after trying `compose-up-gpu`.
- 2026-04-04: Re-validated the GPU-host preflight slice with `pytest tests/smoke/test_verify_gpu_host.py tests/smoke/test_docker_build_cache.py tests/smoke/test_verify_compose_runtime.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_startup_checks.py tests/smoke/test_compose_runtime_config.py -q`, `python3 -m py_compile docker/scripts/verify_gpu_host.py tests/smoke/test_verify_gpu_host.py`, `make validate-compose-gpu-host`, and `git diff --check`. The current host reports `available_runtimes=io.containerd.runc.v2,nvidia,runc`, so the remaining Milestone 14 gap is now the final live GPU-backed `training_worker` boot plus `make validate-compose-gpu-runtime`.
- 2026-04-04: Tightened the successful CUDA startup-check log so a GPU-backed `training_worker` no longer reports misleading `visible_devices=void` values when the container runtime manages device exposure. Successful CUDA logs now normalize empty or `void`-style values to `visible_devices=runtime-managed` while preserving explicit values like `0,1`.
- 2026-04-04: Re-validated the final Milestone 14 GPU-runtime slice with `pytest tests/smoke/test_startup_checks.py tests/smoke/test_verify_training_worker_gpu.py tests/smoke/test_verify_compose_runtime.py tests/smoke/test_verify_gpu_host.py tests/smoke/test_docker_build_cache.py tests/smoke/test_compose_runtime_config.py -q`, `python3 -m py_compile docker/scripts/startup_checks.py tests/smoke/test_startup_checks.py`, `git diff --check`, a rebuilt `make compose-build`, a real high-port GPU-backed `docker compose -f compose.yaml -f docker/compose.gpu.yaml up -d`, a live `make validate-compose-runtime`, and a live `make validate-compose-gpu-runtime`. The stack reached healthy readiness states, `training_worker` reported `CUDA available with 1 device(s) [visible_devices=runtime-managed]: NVIDIA GeForce GTX 1080 Ti`, and Milestone 14 is complete.

---

### Milestone 15: Seed data, smoke tests, docs, and final hardening
**Scope**
- Add seed/demo records where helpful
- Add end-to-end smoke tests for critical path
- Expand README with setup and run instructions
- Document env vars
- Add troubleshooting notes
- Review logging, safety guards, and error handling
- Add CI execution for Playwright smoke tests
- Add stable seeded test environment for browser-based test runs
- Tighten tests for:
  - symbol validation
  - OHLC deduplication
  - pattern detection
  - feature generation
  - approval gating
  - MT5 demo safety
  - signal creation gating
  - API health endpoints
  - frontend critical-path browser flows

**Done when**
- Repo can be set up by another engineer
- Critical flows have automated coverage
- Docs are usable and accurate
- Safety guards are present and visible
- Playwright smoke suite runs reliably in local and CI environments

**Validation**
- Test suite passes
- Playwright smoke suite passes
- README setup followed from clean environment
- Core smoke path works:
  - validate symbol
  - ingest candles
  - preprocess
  - train
  - evaluate
  - approve
  - paper trade

**Progress notes**
- 2026-04-04: Added a dedicated GitHub Actions workflow at `.github/workflows/frontend-playwright-smoke.yml` so the existing seeded frontend browser smoke suite runs automatically on pushes to `main` and on pull requests without requiring backend infrastructure.
- 2026-04-04: Added top-level npm entry points for frontend unit and browser smoke tests, and expanded the root `README.md` with the Playwright browser-install step plus the local `frontend:test:e2e` workflow description tied to the seeded operator fixtures.
- 2026-04-04: Re-validated this Milestone 15 slice with `npm install`, `npm run frontend:test`, `npx playwright install chromium`, `npm run frontend:test:e2e`, and `git diff --check`. Milestone 15 remains in progress because the broader README/env-var/troubleshooting work, additional critical-path smoke coverage, and final hardening items are still outstanding.
- 2026-04-04: Expanded the root `README.md` with a real environment-variable reference and troubleshooting section, including the split Compose worker overrides (`CPU_WORKER_*` and `TRAINING_WORKER_*`), safety-critical paper-trading guards, MT5 degradation expectations, port-conflict handling, and the GPU validation path.
- 2026-04-04: Added `tests/smoke/test_setup_docs.py` so the repo now smoke-checks that `.env.example` keeps the critical runtime, safety, and Compose override variables and that the root README still exposes the environment-variable and troubleshooting sections.
- 2026-04-04: Re-validated this documentation slice with `pytest tests/smoke/test_setup_docs.py -q`, `python3 -m py_compile tests/smoke/test_setup_docs.py`, and `git diff --check`. Milestone 15 remains in progress because broader setup docs, additional end-to-end smoke coverage, and final hardening review work are still outstanding.
- 2026-04-04: Added a dedicated `rl_trade_api.tools.core_workflow_dry_run` command plus `make validate-core-smoke` so the repo now has one repeatable in-process backend smoke path that validates symbol intake, ingestion, preprocessing, supervised training, evaluation/approval, and the demo-only paper-trading lane from a temporary seeded workspace.
- 2026-04-04: Added `tests/smoke/test_core_workflow_dry_run.py` so the command-backed critical-path smoke path is exercised in automated coverage instead of living only as a manual operator command.
- 2026-04-04: Re-validated this critical-path smoke slice with `make validate-core-smoke`, `pytest tests/smoke/test_core_workflow_dry_run.py -q`, `python3 -m py_compile apps/api/src/rl_trade_api/tools/core_workflow_dry_run.py tests/smoke/test_core_workflow_dry_run.py`, and `git diff --check`. Milestone 15 remains in progress because broader docs polish, additional smoke/hardening coverage, and the final completion sweep are still outstanding.
- 2026-04-05: Extended the Milestone 15 core backend smoke path so the temporary FastAPI app now probes `/health`, `/health/db`, `/health/redis`, and `/api/v1/system/status` before running the seeded validate-to-paper-trade workflow, with repo-local overrides that keep DB and Redis health checks deterministic inside the dry run.
- 2026-04-05: Re-validated this API-health smoke slice with `python3 -m py_compile apps/api/src/rl_trade_api/tools/core_workflow_dry_run.py tests/smoke/test_core_workflow_dry_run.py tests/api/test_health.py`, `.venv/bin/python -m pytest tests/api/test_health.py tests/smoke/test_core_workflow_dry_run.py -q` (`4 passed in 31.89s`), and `make validate-core-smoke`. Milestone 15 remains in progress because broader docs polish, additional smoke/hardening coverage, and the final completion sweep are still outstanding.
- 2026-04-05: Added `docs/setup.md` as a dedicated local setup runbook that walks a new engineer through safe `.env` preparation, local process startup, Compose startup, and the repo's milestone smoke commands from install through validation.
- 2026-04-05: Tightened the setup-doc smoke coverage so `tests/smoke/test_setup_docs.py` now asserts the runbook includes clean install steps, safety defaults, runtime startup commands, and the current backend/frontend smoke commands. Re-validated this docs slice with `python3 -m py_compile tests/smoke/test_setup_docs.py`, `.venv/bin/python -m pytest tests/smoke/test_setup_docs.py -q` (`3 passed in 0.01s`), and `git diff --check`. Milestone 15 remains in progress because additional smoke/hardening coverage and the final completion sweep are still outstanding.
- 2026-04-05: Tightened the docs hardening coverage again so `tests/smoke/test_setup_docs.py` now verifies the `make`, `npm run`, and repo-local `python -m rl_trade_*` commands documented in `README.md` and `docs/setup.md` still resolve to real Makefile targets, npm scripts, and importable dry-run modules.
- 2026-04-05: Re-validated this docs/tooling-sync slice with `python3 -m py_compile tests/smoke/test_setup_docs.py`, `.venv/bin/python -m pytest tests/smoke/test_setup_docs.py -q` (`4 passed in 0.02s`), and `git diff --check`. Milestone 15 remains in progress because additional smoke/hardening coverage and the final completion sweep are still outstanding.
- 2026-04-05: Added `.github/workflows/backend-smoke.yml` so GitHub Actions now runs the Milestone 15 backend docs and smoke lane on pull requests and pushes to `main`, covering the setup-doc checks, API health endpoint tests, and the command-backed core validate-to-paper-trade dry run.
- 2026-04-05: Re-validated this backend-CI slice locally with `.venv/bin/python -m pytest tests/smoke/test_setup_docs.py tests/api/test_health.py tests/smoke/test_core_workflow_dry_run.py -q` (`8 passed in 28.53s`), `make validate-core-smoke`, and `git diff --check`. Milestone 15 remains in progress because additional smoke/hardening coverage and the final completion sweep are still outstanding.
- 2026-04-05: Added `make validate-hardening-backend` as a curated Milestone 15 backend regression lane for symbol validation, ingestion dedup/resume behavior, candlestick pattern detection, feature calculations, approval gating, MT5 demo safety, paper-trade gate checks, and the signal-creation API block/allow paths. Wired this lane into `.github/workflows/backend-smoke.yml` so the backend smoke workflow now exercises both the seeded end-to-end dry run and the focused hardening suite.
- 2026-04-05: Re-validated this hardening-regression slice with `make validate-hardening-backend` after fixing an initial `pytest -k` filter mistake that excluded the non-API modules. Final validation passed with `40 passed in 0.62s` for the curated module suite, `3 passed, 11 deselected in 0.50s` for the filtered signal-creation API checks, and `git diff --check`. Milestone 15 remains in progress because the final completion sweep and milestone-wide validation are still outstanding.
- 2026-04-05: Added `tests/smoke/test_ci_workflows.py` so the repo now smoke-checks both GitHub Actions smoke workflows themselves, ensuring the backend workflow still runs the docs/health/core-smoke/hardening commands and the frontend workflow still runs the Playwright install plus frontend unit and browser smoke lanes on pull requests and pushes to `main`.
- 2026-04-05: Re-validated this CI-workflow smoke slice with `python3 -m py_compile tests/smoke/test_ci_workflows.py`, `.venv/bin/python -m pytest tests/smoke/test_ci_workflows.py -q` (`2 passed in 0.01s`), and `git diff --check`. Milestone 15 remains in progress because the final completion sweep and milestone-wide validation are still outstanding.
- 2026-04-05: Added `make validate-milestone15` as a one-command Milestone 15 checkpoint that bundles the docs/workflow smoke tests, API health plus core backend smoke coverage, the curated backend hardening lane, and the frontend unit plus Playwright browser smoke suites. Updated `README.md` and `docs/setup.md` so operators have a documented single-command validation path.
- 2026-04-05: Re-validated this milestone-checkpoint slice with `make validate-milestone15` after fixing two reliability issues discovered during the first runs: the bundled Playwright step now forces a fresh server launch and uses a configurable preview port via `apps/frontend/playwright.config.ts`, with the checkpoint target pinned to `PLAYWRIGHT_PORT=4174` to avoid local `4173` collisions. Final validation passed with `10 passed in 28.92s` for the docs/workflow/health/core-smoke pytest slice, `40 passed in 0.66s` for the curated backend hardening suite, `3 passed, 11 deselected in 0.51s` for the filtered signal-creation API checks, a successful `make validate-core-smoke`, `6 passed` for the frontend Vitest smoke suite, `1 passed (4.8s)` for the Playwright browser smoke suite, and `git diff --check`. Milestone 15 remains in progress because the final completion sweep and milestone-wide validation review are still outstanding.
- 2026-04-05: Replaced the stale placeholder validation-command section in `PLANS.md` with the repo's real Make/npm validation commands for backend, worker, frontend, and infra workflows, so the plan now matches the current Milestone 15 operator path instead of generic TODO text.
- 2026-04-05: Re-validated this plan-alignment slice with `python3 -m py_compile tests/smoke/test_setup_docs.py`, `.venv/bin/python -m pytest tests/smoke/test_setup_docs.py -q` (`5 passed in 0.02s`), and `git diff --check`. Milestone 15 remains in progress because the final completion sweep and milestone-wide validation review are still outstanding.
- 2026-04-05: Added a dedicated `Safety Guarantees` section to `README.md` so the demo-only policy, backend-enforced MT5/live-account blocking, approved-model gate, approval thresholds, fail-safe dependency behavior, and worker-only long-running execution rules are visible in one place for operators and reviewers.
- 2026-04-05: Re-validated this safety-visibility docs slice with `python3 -m py_compile tests/smoke/test_setup_docs.py`, `.venv/bin/python -m pytest tests/smoke/test_setup_docs.py -q` (`5 passed in 0.02s`), and `git diff --check`. Milestone 15 remains in progress because the final completion sweep and milestone-wide validation review are still outstanding.
- 2026-04-05: Continued the Milestone 15 final completion sweep after `make test-backend` exposed two backend regressions: evaluation API tests could fail on custom FastAPI apps that had no `event_broadcaster` state, and the ingestion/preprocessing/supervised-training API tests could no longer monkeypatch the expected enqueue task handles after the service modules switched to fully local worker imports.
- 2026-04-05: Fixed those completion-sweep blockers by making `get_event_broadcaster` lazily install a safe in-process `EventBroadcaster` fallback on app state and by restoring lazy module-level enqueue task handles in the ingestion, preprocessing, and training services so backend task dispatch stays worker-backed while the API compatibility tests can still patch the documented `run_*_job.delay` symbols.
- 2026-04-05: Re-validated this final-sweep blocker slice with `python3 -m py_compile apps/api/src/rl_trade_api/api/deps.py apps/api/src/rl_trade_api/services/ingestion.py apps/api/src/rl_trade_api/services/preprocessing.py apps/api/src/rl_trade_api/services/training.py`, `.venv/bin/python -m pytest tests/api/test_evaluations_api.py tests/api/test_ingestion_api.py tests/api/test_preprocessing_api.py tests/api/test_supervised_training_api.py tests/api/test_training_request_api.py -q` (`21 passed in 2.58s`), `make test-backend` (`194 passed, 1 skipped in 68.68s`), and `make validate-milestone15` (docs/workflow smoke `11 passed in 29.45s`, curated hardening `40 passed in 0.65s`, trading gate API checks `3 passed, 11 deselected in 0.51s`, successful core workflow dry run, frontend Vitest `6 passed`, and Playwright browser smoke `1 passed in 4.7s`). Milestone 15 remains in progress pending an explicit clean-environment setup validation against the README/setup runbook before the milestone can be marked complete.
- 2026-04-05: Added `rl_trade_api.tools.validate_clean_setup` plus `make validate-clean-setup` so the repo now has a command-backed clean-room setup proof that copies the current workspace into a temporary directory, copies `.env.example` to `.env`, creates a fresh virtualenv, installs the editable backend package, validates backend bootstrap, installs frontend dependencies, installs Playwright Chromium, and runs the frontend unit smoke suite without mutating the main workspace.
- 2026-04-05: Updated `README.md`, `docs/setup.md`, `Makefile`, and the setup-doc smoke coverage so the clean-setup validator is documented, included in the Milestone 15 operator path, and covered by `tests/smoke/test_clean_setup_validation.py` plus the existing docs/tooling-sync checks.
- 2026-04-05: Re-validated the clean-setup and final completion slice with `python3 -m py_compile apps/api/src/rl_trade_api/tools/validate_clean_setup.py tests/smoke/test_clean_setup_validation.py tests/smoke/test_setup_docs.py`, `.venv/bin/python -m pytest tests/smoke/test_clean_setup_validation.py tests/smoke/test_setup_docs.py -q` (`6 passed in 0.09s`), `make validate-clean-setup` (temporary workspace setup proof completed successfully, including fresh backend install, backend bootstrap validation, `npm install`, `npx playwright install --with-deps chromium`, and frontend Vitest smoke), `make validate-milestone15` (docs/workflow smoke `12 passed in 29.45s`, curated hardening `40 passed in 0.67s`, trading gate API checks `3 passed, 11 deselected in 0.52s`, successful core workflow dry run, frontend Vitest `6 passed`, and Playwright browser smoke `1 passed in 4.7s`), and `make test-backend` (`195 passed, 1 skipped in 70.17s`). Milestone 15 is complete.

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
These commands reflect the current repo tooling for the Milestone 15 validation surface.

### Backend
- `make test-backend`
- `make validate-backend`
- `make validate-core-smoke`
- `make validate-hardening-backend`
- `make validate-clean-setup`
- `make validate-milestone15`
- `make run-api`

### Worker
- `make run-worker`
- `make run-scheduler`
- `make validate-core-smoke`

### Frontend
- `npm install`
- `npm run frontend:test`
- `npm run frontend:test:e2e`
- `make validate-frontend`

### Infra
- `make db-upgrade`
- `make validate-db`
- `make validate-db-timescale`
- `make validate-compose`
- `make compose-build`
- `make compose-up`
- `make compose-down`

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
