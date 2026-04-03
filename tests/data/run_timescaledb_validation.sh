#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
CONTAINER_NAME="${TIMESCALE_CONTAINER_NAME:-rl-trade-timescaledb-test}"
IMAGE="${TIMESCALE_IMAGE:-timescale/timescaledb:latest-pg16}"
PORT="${TIMESCALE_PORT:-55432}"
POSTGRES_USER="${TIMESCALE_POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${TIMESCALE_POSTGRES_PASSWORD:-postgres}"
POSTGRES_DB="${TIMESCALE_POSTGRES_DB:-rl_trade_test}"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}

trap cleanup EXIT
cleanup

docker run -d \
  --rm \
  --name "${CONTAINER_NAME}" \
  -e POSTGRES_USER="${POSTGRES_USER}" \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -e POSTGRES_DB="${POSTGRES_DB}" \
  -p "${PORT}:5432" \
  "${IMAGE}" >/dev/null

export RL_TRADE_TEST_POSTGRES_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${PORT}/${POSTGRES_DB}"

for _ in $(seq 1 60); do
  if docker logs "${CONTAINER_NAME}" 2>&1 | grep -q "PostgreSQL init process complete; ready for start up." && \
    docker exec "${CONTAINER_NAME}" pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1 && \
    RL_TRADE_TEST_POSTGRES_URL="${RL_TRADE_TEST_POSTGRES_URL}" "${PYTHON_BIN}" - <<'PY'
import os
import sys
from sqlalchemy import create_engine, text

try:
    engine = create_engine(os.environ["RL_TRADE_TEST_POSTGRES_URL"])
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    engine.dispose()
except Exception:
    sys.exit(1)
PY
  then
    "${PYTHON_BIN}" -m pytest tests/data/test_timescale_integration.py
    exit 0
  fi
  sleep 1
done

echo "TimescaleDB container did not become ready in time." >&2
exit 1
