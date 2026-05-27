#!/usr/bin/env bash
# Настраивает Yandex Cloud Foundation Models в .env (API-ключ + folder id).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
  echo "Created $ENV_FILE from .env.example"
fi

if grep -q '^YANDEX_API_KEY=.\+' "$ENV_FILE" 2>/dev/null && grep -q '^YANDEX_FOLDER_ID=.\+' "$ENV_FILE" 2>/dev/null; then
  echo "Yandex LLM already configured in $ENV_FILE"
  exit 0
fi

if [[ -n "${YANDEX_API_KEY:-}" && -n "${YANDEX_FOLDER_ID:-}" ]]; then
  echo "Using YANDEX_API_KEY and YANDEX_FOLDER_ID from environment"
  FOLDER_ID="$YANDEX_FOLDER_ID"
  API_KEY_SECRET="$YANDEX_API_KEY"
else
  YC_BIN="${YC_BIN:-yc}"
  if ! command -v "$YC_BIN" >/dev/null 2>&1; then
    echo "Yandex CLI (yc) not found and YANDEX_* env vars are empty." >&2
    echo "Install: curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash" >&2
    echo "Then: yc init && make setup-yandex" >&2
    exit 1
  fi

  FOLDER_ID="$("$YC_BIN" config get folder-id 2>/dev/null || true)"
  if [[ -z "$FOLDER_ID" ]]; then
    echo "Run 'yc init' and select a folder, or set YANDEX_FOLDER_ID." >&2
    exit 1
  fi

  SA_NAME="${YANDEX_SA_NAME:-prikazy-llm}"
  SA_ID="$("$YC_BIN" iam service-account list --folder-id "$FOLDER_ID" --format json \
    | python3 -c "import json,sys; name=sys.argv[1]; print(next((x['id'] for x in json.load(sys.stdin) if x['name']==name), ''))" "$SA_NAME")"

  if [[ -z "$SA_ID" ]]; then
    echo "Creating service account $SA_NAME..."
    SA_ID="$("$YC_BIN" iam service-account create --name "$SA_NAME" --folder-id "$FOLDER_ID" --format json \
      | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")"
  fi

  "$YC_BIN" resource-manager folder add-access-binding "$FOLDER_ID" \
    --role ai.languageModels.user \
    --subject "serviceAccount:$SA_ID" >/dev/null 2>&1 || true

  echo "Creating API key for service account..."
  API_KEY_JSON="$("$YC_BIN" iam api-key create \
    --service-account-id "$SA_ID" \
    --scope yc.ai.foundationModels.execute \
    --format json)"
  API_KEY_SECRET="$(python3 -c "import json,sys; print(json.load(sys.stdin)['secret'])" <<<"$API_KEY_JSON")"
fi

python3 <<PY
from pathlib import Path

env_path = Path("$ENV_FILE")
lines = env_path.read_text(encoding="utf-8").splitlines()
updates = {
    "LLM_PROVIDER": "yandex",
    "YANDEX_FOLDER_ID": "$FOLDER_ID",
    "YANDEX_API_KEY": "$API_KEY_SECRET",
    "YANDEX_MODEL": "yandexgpt-lite/latest",
}
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line and not line.strip().startswith("#") else None
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
env_path.write_text("\\n".join(out) + "\\n", encoding="utf-8")
print(f"Updated {env_path} with Yandex LLM settings (folder={updates['YANDEX_FOLDER_ID'][:8]}…)")
PY

echo "Done. Restart app: docker compose restart app"
