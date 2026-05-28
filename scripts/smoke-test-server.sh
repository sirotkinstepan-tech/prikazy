#!/usr/bin/env bash
# End-to-end smoke test against a running Prikazy instance.
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8001}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-admin123}"
SAMPLE="${SAMPLE:-samples/sample.pdf}"
COOKIE_JAR="$(mktemp)"
CSRF_FILE="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$CSRF_FILE"' EXIT

echo "==> Health"
curl -fsS "$API_BASE/health" | grep -q '"status":"ok"'

echo "==> Sections"
curl -fsS "$API_BASE/sections" | grep -q prikaz

echo "==> Login"
API_BASE="$API_BASE" EMAIL="$EMAIL" PASSWORD="$PASSWORD" \
  COOKIE_JAR="$COOKIE_JAR" CSRF_FILE="$CSRF_FILE" \
  "$(dirname "$0")/api-session.sh"

echo "==> Upload"
curl -fsS -X POST "$API_BASE/documents/upload" \
  -b "$COOKIE_JAR" \
  -H "X-CSRF-Token: $(cat "$CSRF_FILE")" \
  -F "doc_type=prikaz" \
  -F "title=Smoke test" \
  -F "file=@$SAMPLE;type=application/pdf" | grep -q document_id

echo "==> Portal HTML"
curl -fsS "$API_BASE/portal/" -b "$COOKIE_JAR" | grep -qi portal

echo "==> Search (may be empty until OCR finishes)"
curl -fsS --get "$API_BASE/search" -b "$COOKIE_JAR" --data-urlencode "q=smoke" >/dev/null

echo "All smoke checks passed for $API_BASE"
