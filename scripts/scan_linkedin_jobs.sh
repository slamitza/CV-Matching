#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

CONFIG="$ROOT_DIR/config/settings.toml"
if [ ! -f "$CONFIG" ]; then
  CONFIG="$ROOT_DIR/config/settings.example.toml"
  printf '%s\n' "warning: config/settings.toml not found; using config/settings.example.toml" >&2
fi

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  scan --source linkedin-browser

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  new-jobs --source linkedin-browser

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  export-jobs --source linkedin-browser --out "$ROOT_DIR/reports/linkedin_jobs.csv"
