#!/usr/bin/env bash
# Role-based smoke tests against running API (local dev).
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8001}"
WORKDIR="${WORKDIR:-/tmp/prikazy-role-test}"
mkdir -p "$WORKDIR"

log() { printf '\n=== %s ===\n' "$1"; }
status_code() { curl -s -o /dev/null -w "%{http_code}" "$@"; }

login_as() {
  local role="$1" email="$2" password="$3"
  local jar="$WORKDIR/cookies-$role.txt"
  local csrf_file="$WORKDIR/csrf-$role.txt"
  rm -f "$jar" "$csrf_file"
  local page csrf
  page=$(curl -s -c "$jar" "$API_BASE/login")
  csrf=$(printf '%s' "$page" | sed -n 's/.*name="csrf_token" value="\([^"]*\)".*/\1/p' | head -1)
  curl -s -b "$jar" -c "$jar" -X POST "$API_BASE/login" \
    --data-urlencode "email=$email" \
    --data-urlencode "password=$password" \
    --data-urlencode "csrf_token=$csrf" \
    -o /dev/null
  curl -s -b "$jar" "$API_BASE/auth/csrf" | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])' > "$csrf_file"
  echo "$jar|$csrf_file"
}

session_get() {
  local jar="$1" path="$2"
  curl -s -b "$jar" -o /dev/null -w "%{http_code}" "$API_BASE$path"
}

session_get_follow() {
  local jar="$1" path="$2"
  curl -s -b "$jar" -L -o /dev/null -w "%{http_code} final:%{url_effective}" "$API_BASE$path"
}

log "Guest"
echo "health: $(curl -s "$API_BASE/health" | head -c 80)"
echo "documents API: $(status_code "$API_BASE/documents?limit=1")"
echo "portal: $(status_code -L "$API_BASE/portal/")"
echo "admin: $(status_code -L "$API_BASE/admin/")"
echo "viewer: $(status_code -L "$API_BASE/viewer")"

log "Admin login"
IFS='|' read -r ADMIN_JAR ADMIN_CSRF <<< "$(login_as admin admin@example.com admin123)"
echo "portal after login: $(session_get_follow "$ADMIN_JAR" "/portal/")"
echo "admin dashboard: $(session_get "$ADMIN_JAR" "/admin/")"
echo "documents API: $(session_get "$ADMIN_JAR" "/documents?limit=1")"
echo "users page: $(session_get "$ADMIN_JAR" "/admin/users")"
echo "upload page: $(session_get "$ADMIN_JAR" "/admin/upload")"
echo "viewer: $(session_get "$ADMIN_JAR" "/viewer")"

log "Employee login"
IFS='|' read -r EMP_JAR EMP_CSRF <<< "$(login_as employee employee@example.com employee123)"
echo "portal home: $(session_get "$EMP_JAR" "/portal/")"
echo "admin blocked: $(session_get_follow "$EMP_JAR" "/admin/")"
echo "documents API: $(session_get "$EMP_JAR" "/documents?limit=1")"
echo "upload page: $(session_get "$EMP_JAR" "/portal/upload")"

log "Admin API upload (tiny PDF)"
printf '%%PDF-1.4\n%%EOF' > "$WORKDIR/tiny.pdf"
UP=$(curl -s -b "$ADMIN_JAR" -H "X-CSRF-Token: $(cat "$ADMIN_CSRF")" -X POST "$API_BASE/documents/upload" \
  -F "doc_type=prikaz" -F "file=@$WORKDIR/tiny.pdf;type=application/pdf")
echo "$UP" | head -c 200
DOC_ID=$(printf '%s' "$UP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("document_id",""))' 2>/dev/null || true)
if [[ -n "$DOC_ID" ]]; then
  echo "get document: $(session_get "$ADMIN_JAR" "/documents/$DOC_ID")"
  echo "download: $(status_code -b "$ADMIN_JAR" "$API_BASE/documents/$DOC_ID/download")"
fi

log "Done"
