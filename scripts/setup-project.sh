#!/usr/bin/env bash
# Полная локальная настройка: .env, секрет сессии, Yandex LLM (если доступен yc).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env"
fi

if ! grep -q '^SESSION_SECRET=change-me' .env; then
  :
else
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  if [[ "$(uname)" == Darwin ]]; then
    sed -i '' "s|^SESSION_SECRET=.*|SESSION_SECRET=$SECRET|" .env
  else
    sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=$SECRET|" .env
  fi
  echo "Generated SESSION_SECRET"
fi

chmod +x scripts/setup-yandex-llm.sh
if ./scripts/setup-yandex-llm.sh; then
  echo "Yandex LLM configured."
else
  echo "Yandex LLM not configured yet (need yc init or YANDEX_* env vars)."
fi

echo "Next: make up && make migrate && make seed"
