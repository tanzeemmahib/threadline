#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_python="${repo_root}/backend/.venv/bin/python"
bootstrap=0
forward=()

for argument in "$@"; do
  case "$argument" in
    --bootstrap) bootstrap=1 ;;
    *) forward+=("$argument") ;;
  esac
done

if [[ "$bootstrap" == "1" ]]; then
  if [[ ! -x "$backend_python" ]]; then
    "${PYTHON:-python3}" -m venv "${repo_root}/backend/.venv"
  fi
  "$backend_python" -m pip install \
    -r "${repo_root}/backend/requirements-dev.txt" \
    -r "${repo_root}/docs/requirements.txt"
  (cd "${repo_root}/frontend" && npm ci)
  (cd "${repo_root}/frontend" && npx playwright install chromium)
fi

release_python="${THREADLINE_RELEASE_PYTHON:-$backend_python}"
if [[ ! -x "$release_python" ]]; then
  release_python="${PYTHON:-python3}"
fi

exec "$release_python" "${repo_root}/scripts/reverie_release.py" \
  --backend-python "$release_python" \
  --pdf-python "$release_python" \
  "${forward[@]}"
