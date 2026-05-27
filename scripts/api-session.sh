#!/usr/bin/env bash
# Obtain session cookie and CSRF token for authenticated API calls (local dev).
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8001}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-admin123}"
COOKIE_JAR="${COOKIE_JAR:-.api-cookies.txt}"
CSRF_FILE="${CSRF_FILE:-.api-csrf-token}"

login_page=$(curl -s -c "$COOKIE_JAR" "$API_BASE/login")
csrf=$(printf '%s' "$login_page" | sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p' | head -1)
if [[ -z "$csrf" ]]; then
  echo "Failed to extract CSRF token from /login" >&2
  exit 1
fi

curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" -X POST "$API_BASE/login" \
  --data-urlencode "email=$EMAIL" \
  --data-urlencode "password=$PASSWORD" \
  --data-urlencode "csrf_token=$csrf" \
  -o /dev/null

curl -s -b "$COOKIE_JAR" "$API_BASE/auth/csrf" | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])' > "$CSRF_FILE"
echo "Session saved to $COOKIE_JAR, CSRF token to $CSRF_FILE"
