#!/usr/bin/env bash
# Bootstrap + deploy Prikazy on a fresh Ubuntu VM (run as root or with sudo).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/sirotkinstepan-tech/prikazy.git}"
APP_DIR="${APP_DIR:-/opt/prikazy}"
BRANCH="${BRANCH:-main}"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-kmk-base.ru}"
PUBLIC_HOST="${PUBLIC_HOST:-}"

if [[ -z "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST="$(curl -fsS --max-time 5 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
fi
if [[ -z "$PUBLIC_HOST" ]]; then
  PUBLIC_HOST="$(hostname -I | awk '{print $1}')"
fi

if [[ -n "$PUBLIC_DOMAIN" ]]; then
  PUBLIC_API_BASE_URL="https://${PUBLIC_DOMAIN}"
  SESSION_HTTPS_ONLY="true"
else
  PUBLIC_API_BASE_URL="http://${PUBLIC_HOST}:8001"
  SESSION_HTTPS_ONLY="false"
fi

echo "==> Installing Docker (if needed)"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
fi

echo "==> Cloning/updating repository at $APP_DIR"
if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH" || git reset --hard "origin/$BRANCH"

echo "==> Preparing .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
S3_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"

export PUBLIC_HOST PUBLIC_DOMAIN PUBLIC_API_BASE_URL SESSION_HTTPS_ONLY

python3 <<PY
from pathlib import Path
import os
import re

path = Path(".env")
text = path.read_text()
updates = {
    "APP_ENV": "production",
    "APP_DEBUG": "false",
    "DOCS_ENABLED": "true",
    "SESSION_HTTPS_ONLY": os.environ.get("SESSION_HTTPS_ONLY", "false"),
    "PUBLIC_API_BASE_URL": os.environ.get("PUBLIC_API_BASE_URL", "http://localhost:8001"),
    "SESSION_SECRET": "$SESSION_SECRET",
    "POSTGRES_PASSWORD": "$POSTGRES_PASSWORD",
    "DATABASE_URL": "postgresql+psycopg://prikazy:$POSTGRES_PASSWORD@postgres:5432/prikazy",
    "S3_SECRET_ACCESS_KEY": "$S3_SECRET",
}
for key, val in updates.items():
    if re.search(rf"^{re.escape(key)}=", text, re.M):
        text = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={val}", text, flags=re.M)
    else:
        text += f"\n{key}={val}\n"
path.write_text(text)
PY

echo "==> Building and starting stack"
export DOCKER_BUILDKIT=0
docker compose -f docker-compose.prod.yml up -d --build

echo "==> Waiting for PostgreSQL"
for i in $(seq 1 30); do
  if docker compose -f docker-compose.prod.yml exec -T postgres pg_isready -U prikazy -d prikazy >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Migrations and seed"
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head
docker compose -f docker-compose.prod.yml exec -T app python scripts/seed_users.py || true

echo "==> Health check"
curl -fsS "http://127.0.0.1:8001/health"

echo ""
if [[ -n "$PUBLIC_DOMAIN" ]]; then
  echo "Deployed. Portal: https://${PUBLIC_DOMAIN}/portal/"
  echo "Run domain setup: sudo PUBLIC_DOMAIN=${PUBLIC_DOMAIN} bash scripts/setup-domain.sh"
else
  echo "Deployed. Portal: http://${PUBLIC_HOST}:8001/portal/"
fi
echo "Admin login: admin@example.com / admin123 (change after first login)"
