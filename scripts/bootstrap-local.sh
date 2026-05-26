#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL="$ROOT/.local"
STAGING="$LOCAL/staging"

mkdir -p "$LOCAL/bin" "$STAGING"

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Creating Python 3.12 venv..."
cd "$ROOT"
uv venv --python 3.12 .venv312
# shellcheck disable=SC1091
source .venv312/bin/activate
uv pip install -e ".[dev]"

if [[ ! -x "$LOCAL/bin/minio" ]]; then
  echo "Downloading MinIO..."
  curl -fsSL -o "$LOCAL/bin/minio" "https://dl.min.io/server/minio/release/darwin-arm64/minio"
  chmod +x "$LOCAL/bin/minio"
fi

if [[ ! -x "$STAGING/pgsql/bin/postgres" ]]; then
  echo "Downloading PostgreSQL 16 binaries (~340 MB)..."
  curl -fL -o "$STAGING/postgresql-binaries.zip" \
    "https://get.enterprisedb.com/postgresql/postgresql-16.14-1-osx-binaries.zip"
  unzip -q -o "$STAGING/postgresql-binaries.zip" -d "$STAGING"
fi

if [[ ! -x /tmp/redis-7.2.7/src/redis-server ]]; then
  echo "Building Redis from source..."
  curl -fsSL -o /tmp/redis.tar.gz "https://github.com/redis/redis/archive/refs/tags/7.2.7.tar.gz"
  tar -xzf /tmp/redis.tar.gz -C /tmp
  make -C /tmp/redis-7.2.7 -j4 >/dev/null
fi

if [[ ! -f "$ROOT/.env.local" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env.local"
  sed -i '' \
    -e 's|@postgres:5432|@localhost:5433|g' \
    -e 's|redis://redis:|redis://localhost:6380|g' \
    -e 's|redis://localhost:6379|redis://localhost:6380|g' \
    -e 's|http://minio:9000|http://localhost:9002|g' \
    -e 's|http://localhost:9000|http://localhost:9002|g' \
    "$ROOT/.env.local"
fi

python3 <<'PY'
from pathlib import Path

sample = Path("samples/sample.pdf")
sample.parent.mkdir(parents=True, exist_ok=True)
if not sample.exists():
    # Minimal valid PDF with searchable text for OCR stub testing.
    sample.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<<>>endobj\n"
        b"2 0 obj<< /Length 44 >>stream\n"
        b"BT /F1 12 Tf 100 700 Td (INVOICE ACME 2026) Tj ET\n"
        b"endstream\nendobj\n"
        b"3 0 obj<< /Type /Catalog /Pages 4 0 R >>endobj\n"
        b"4 0 obj<< /Type /Pages /Kids [5 0 R] /Count 1 >>endobj\n"
        b"5 0 obj<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] >>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"trailer<< /Size 6 /Root 3 0 R >>\nstartxref\n0\n%%EOF\n"
    )
    print(f"Created {sample}")
PY

echo "Bootstrap complete. Run: scripts/local-dev-up.sh"
