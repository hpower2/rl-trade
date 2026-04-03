PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
NPM ?= npm

.PHONY: install-backend install-frontend test-backend validate-backend validate-db validate-db-timescale validate-frontend db-upgrade db-downgrade-base run-api run-worker run-scheduler run-frontend

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
