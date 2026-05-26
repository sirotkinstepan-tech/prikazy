#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL="$ROOT/.local"
PG_BIN="$LOCAL/staging/pgsql/bin"
REDIS_BIN="/tmp/redis-7.2.7/src"
MINIO_BIN="$LOCAL/bin/minio"
ENV_FILE="$ROOT/.env.local"
VENV="$ROOT/.venv312"
LOG_DIR="$LOCAL/logs"
PID_DIR="$LOCAL/pids"
PGDATA="$LOCAL/data/postgres-prikazy"
REDIS_DIR="$LOCAL/data/redis-prikazy"
MINIO_DIR="$LOCAL/data/minio-prikazy"

PG_PORT=5433
REDIS_PORT=6380
MINIO_API_PORT=9002
MINIO_CONSOLE_PORT=9003
API_PORT=8001

mkdir -p "$LOG_DIR" "$PID_DIR" "$REDIS_DIR" "$MINIO_DIR"

if [[ ! -x "$PG_BIN/postgres" ]]; then
  echo "PostgreSQL binaries not found. Run scripts/bootstrap-local.sh first." >&2
  exit 1
fi

if [[ ! -x "$REDIS_BIN/redis-server" ]]; then
  echo "Redis server not found. Run scripts/bootstrap-local.sh first." >&2
  exit 1
fi

if [[ ! -x "$MINIO_BIN" ]]; then
  echo "MinIO binary not found. Run scripts/bootstrap-local.sh first." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
  sed -i '' \
    -e 's|@postgres:5432|@localhost:5433|g' \
    -e 's|redis://redis:|redis://localhost:6380|g' \
    -e 's|redis://localhost:6379|redis://localhost:6380|g' \
    -e 's|http://minio:9000|http://localhost:9002|g' \
    -e 's|http://localhost:9000|http://localhost:9002|g' \
    "$ENV_FILE"
fi

start_postgres() {
  if "$PG_BIN/pg_isready" -h localhost -p "$PG_PORT" -U prikazy -d prikazy >/dev/null 2>&1; then
    echo "PostgreSQL already running"
    return
  fi

  if [[ ! -d "$PGDATA" ]]; then
    echo "Initializing PostgreSQL cluster..."
    "$PG_BIN/initdb" -D "$PGDATA" -U "$USER" --encoding=UTF8 --locale=C >/dev/null
    cat >> "$PGDATA/postgresql.conf" <<EOF
port = $PG_PORT
listen_addresses = 'localhost'
max_connections = 100
shared_buffers = 128MB
EOF
    cat >> "$PGDATA/pg_hba.conf" <<EOF
host all all 127.0.0.1/32 trust
host all all ::1/128 trust
EOF
  fi

  "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$LOG_DIR/postgres.log" start -w
  sleep 1

  if ! "$PG_BIN/psql" -h localhost -p "$PG_PORT" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='prikazy'" | grep -q 1; then
    "$PG_BIN/psql" -h localhost -p "$PG_PORT" -d postgres -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE prikazy WITH LOGIN PASSWORD 'prikazy' CREATEDB;
CREATE DATABASE prikazy OWNER prikazy;
SQL
  fi
  echo "PostgreSQL started on port $PG_PORT"
}

start_redis() {
  if [[ -f "$PID_DIR/redis.pid" ]] && kill -0 "$(cat "$PID_DIR/redis.pid")" 2>/dev/null; then
    echo "Redis already running"
    return
  fi

  "$REDIS_BIN/redis-server" --daemonize yes \
    --port "$REDIS_PORT" \
    --dir "$REDIS_DIR" \
    --logfile "$LOG_DIR/redis.log" \
    --pidfile "$PID_DIR/redis.pid"
  echo "Redis started on port $REDIS_PORT"
}

start_minio() {
  if [[ -f "$PID_DIR/minio.pid" ]] && kill -0 "$(cat "$PID_DIR/minio.pid")" 2>/dev/null; then
    echo "MinIO already running"
    return
  fi

  MINIO_ROOT_USER=minioadmin MINIO_ROOT_PASSWORD=minioadmin \
    nohup "$MINIO_BIN" server "$MINIO_DIR" \
      --address ":$MINIO_API_PORT" --console-address ":$MINIO_CONSOLE_PORT" \
    > "$LOG_DIR/minio.log" 2>&1 &
  echo $! > "$PID_DIR/minio.pid"
  sleep 2
  echo "MinIO started (API http://localhost:$MINIO_API_PORT, console http://localhost:$MINIO_CONSOLE_PORT)"
}

start_postgres
start_redis
start_minio

export PATH="$HOME/.local/bin:$PATH"
if [[ ! -d "$VENV" ]]; then
  echo "Python venv missing. Run scripts/bootstrap-local.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "Applying migrations..."
alembic upgrade head

if [[ -f "$PID_DIR/api.pid" ]] && kill -0 "$(cat "$PID_DIR/api.pid")" 2>/dev/null; then
  echo "API already running"
else
  nohup uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" > "$LOG_DIR/api.log" 2>&1 &
  echo $! > "$PID_DIR/api.pid"
  echo "API started at http://localhost:$API_PORT"
fi

if [[ -f "$PID_DIR/worker.pid" ]] && kill -0 "$(cat "$PID_DIR/worker.pid")" 2>/dev/null; then
  echo "Worker already running"
else
  nohup celery -A app.workers.celery_app:celery_app worker --loglevel=INFO -Q ocr \
    > "$LOG_DIR/worker.log" 2>&1 &
  echo $! > "$PID_DIR/worker.pid"
  echo "Celery worker started"
fi

sleep 2
curl -sf "http://localhost:$API_PORT/health" | python3 -m json.tool
echo
echo "Ready. Docs: http://localhost:$API_PORT/docs"
echo "Logs: $LOG_DIR"
echo "Stop: scripts/local-dev-down.sh"
