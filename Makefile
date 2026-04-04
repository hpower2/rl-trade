PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
NPM ?= npm
DOCKER_BUILDKIT ?= 1

.PHONY: install-backend install-frontend test-backend validate-backend validate-db validate-db-timescale validate-frontend validate-core-smoke validate-compose validate-compose-gpu validate-compose-runtime validate-compose-gpu-host validate-compose-gpu-runtime compose-build compose-up compose-up-gpu compose-down compose-ps db-upgrade db-downgrade-base run-api run-worker run-scheduler run-frontend

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
