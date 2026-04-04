# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini /app/

RUN python - <<'PY' > /tmp/requirements-runtime.txt
import tomllib

with open("/app/pyproject.toml", "rb") as handle:
    project = tomllib.load(handle)["project"]

for dependency in project["dependencies"]:
    print(dependency)
PY

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements-runtime.txt

COPY alembic /app/alembic
COPY apps /app/apps
COPY libs /app/libs
COPY docker/scripts /app/docker/scripts

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --no-deps -e .

EXPOSE 8000
