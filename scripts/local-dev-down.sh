#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL="$ROOT/.local"
PG_BIN="$LOCAL/staging/pgsql/bin"
REDIS_BIN="/tmp/redis-7.2.7/src"
PID_DIR="$LOCAL/pids"
PGDATA="$LOCAL/data/postgres"

stop_pidfile() {
  local name="$1"
  local pidfile="$PID_DIR/$name.pid"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "Stopped $name (pid $pid)"
    fi
    rm -f "$pidfile"
  fi
}

stop_pidfile api
stop_pidfile worker
stop_pidfile minio

if [[ -f "$PID_DIR/redis.pid" ]]; then
  "$REDIS_BIN/redis-cli" -p 6379 shutdown nosave >/dev/null 2>&1 || true
  rm -f "$PID_DIR/redis.pid"
  echo "Stopped redis"
fi

if [[ -d "$PGDATA" ]]; then
  "$PG_BIN/pg_ctl" -D "$PGDATA" stop -m fast >/dev/null 2>&1 || true
  echo "Stopped postgres"
fi

echo "Local stack stopped."
