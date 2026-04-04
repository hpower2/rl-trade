#!/bin/sh
set -eu

SERVICE_NAME="${1:?service name is required}"
shift

python /app/docker/scripts/startup_checks.py --service "${SERVICE_NAME}"
exec "$@"
