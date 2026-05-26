#!/usr/bin/env bash
# Создаёт репозиторий sirotkinstepan-tech/prikazy и пушит main.
# Требуется: gh auth login (один раз).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GH="${GH:-gh}"
if ! command -v "$GH" >/dev/null 2>&1; then
  if [[ -x /tmp/gh-install/gh_2.69.0_macOS_arm64/bin/gh ]]; then
    GH=/tmp/gh-install/gh_2.69.0_macOS_arm64/bin/gh
  else
    echo "Установите GitHub CLI: https://cli.github.com/" >&2
    exit 1
  fi
fi

"$GH" auth status >/dev/null

if git remote get-url origin >/dev/null 2>&1; then
  git remote remove origin
fi

"$GH" repo create sirotkinstepan-tech/prikazy --public --source=. --remote=origin --push --description "Платформа загрузки, OCR и поиска приказов и документов"

echo "Готово: https://github.com/sirotkinstepan-tech/prikazy"
