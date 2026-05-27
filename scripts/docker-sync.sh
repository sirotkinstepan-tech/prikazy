#!/usr/bin/env bash
# Force-sync project files into running Docker containers when iCloud Drive
# delays volume updates (common on macOS).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_CONTAINER="${APP_CONTAINER:-prikazy-app-1}"
WORKER_CONTAINER="${WORKER_CONTAINER:-prikazy-worker-1}"

for container in "$APP_CONTAINER" "$WORKER_CONTAINER"; do
  if ! docker inspect "$container" >/dev/null 2>&1; then
    echo "skip $container (not running)" >&2
    continue
  fi
  echo "sync -> $container"
  docker cp "$ROOT/app/." "$container:/app/app/"
  docker cp "$ROOT/tests/." "$container:/app/tests/"
  docker cp "$ROOT/scripts/." "$container:/app/scripts/"
  docker cp "$ROOT/templates/." "$container:/app/templates/"
  docker cp "$ROOT/static/." "$container:/app/static/"
  docker cp "$ROOT/alembic/." "$container:/app/alembic/"
  docker cp "$ROOT/pyproject.toml" "$container:/app/pyproject.toml"
done

echo "done"
