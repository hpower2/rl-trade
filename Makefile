PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
NPM ?= npm
DOCKER_BUILDKIT ?= 1

.PHONY: install-backend install-frontend test-backend validate-backend validate-db validate-db-timescale validate-frontend validate-core-smoke validate-hardening-backend validate-clean-setup validate-milestone15 validate-compose validate-compose-gpu validate-compose-runtime validate-compose-gpu-host validate-compose-gpu-runtime compose-build compose-up compose-up-gpu compose-down compose-ps db-upgrade db-downgrade-base run-api run-worker run-scheduler run-frontend

install-backend:
	$(PYTHON) -m pip install -e .[dev]

install-frontend:
	$(NPM) install

test-backend:
	$(PYTHON) -m pytest

validate-backend:
	$(PYTHON) -c "from rl_trade_common import get_settings; from rl_trade_api.main import app; from rl_trade_worker.celery_app import celery_app; print(get_settings().app_name, app.title, celery_app.main)"

validate-db:
	$(PYTHON) -m pytest tests/data

validate-db-timescale:
	PYTHON_BIN=$(PYTHON) ./tests/data/run_timescaledb_validation.sh

validate-frontend:
	$(NPM) run frontend:build

validate-core-smoke:
	$(PYTHON) -m rl_trade_api.tools.core_workflow_dry_run

validate-hardening-backend:
	$(PYTHON) -m pytest \
		tests/trading/test_symbol_validation_core.py \
		tests/worker/test_ingestion_worker.py \
		tests/features/test_candlestick_patterns.py \
		tests/features/test_feature_calculations.py \
		tests/trading/test_approval_gate.py \
		tests/trading/test_mt5_gateway.py \
		tests/trading/test_paper_trade_guard.py
	$(PYTHON) -m pytest \
		tests/api/test_trading_api.py \
		-k "test_create_signal_persists_accepted_signal_and_audit_log or test_create_signal_blocks_unapproved_symbol_and_records_audit_log or test_create_signal_blocks_live_account"

validate-clean-setup:
	$(PYTHON) -m rl_trade_api.tools.validate_clean_setup

validate-milestone15:
	$(PYTHON) -m pytest \
		tests/smoke/test_clean_setup_validation.py \
		tests/smoke/test_setup_docs.py \
		tests/smoke/test_ci_workflows.py \
		tests/api/test_health.py \
		tests/smoke/test_core_workflow_dry_run.py \
		-q
	$(MAKE) validate-hardening-backend
	$(MAKE) validate-core-smoke
	$(NPM) run frontend:test
	CI=1 PLAYWRIGHT_PORT=4174 $(NPM) run frontend:test:e2e

validate-compose:
	docker compose config

validate-compose-gpu:
	docker compose -f compose.yaml -f docker/compose.gpu.yaml config

validate-compose-runtime:
	$(PYTHON) docker/scripts/verify_compose_runtime.py

validate-compose-gpu-host:
	$(PYTHON) docker/scripts/verify_gpu_host.py

validate-compose-gpu-runtime:
	$(PYTHON) docker/scripts/verify_training_worker_gpu.py

compose-build:
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build -t rl-trade-python:local -f docker/python.Dockerfile .
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build -t rl-trade-frontend:latest -f docker/frontend.Dockerfile .

compose-up:
	docker compose up -d

compose-up-gpu:
	docker compose -f compose.yaml -f docker/compose.gpu.yaml up -d

compose-down:
	docker compose down --remove-orphans

compose-ps:
	docker compose ps

db-upgrade:
	$(PYTHON) -m alembic upgrade head

db-downgrade-base:
	$(PYTHON) -m alembic downgrade base

run-api:
	$(PYTHON) -m rl_trade_api.main

run-worker:
	$(PYTHON) -m rl_trade_worker.main

run-scheduler:
	$(PYTHON) -m rl_trade_worker.scheduler

run-frontend:
	$(NPM) run frontend:dev
