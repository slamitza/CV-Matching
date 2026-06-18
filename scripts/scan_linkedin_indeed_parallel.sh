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
  scan-parallel --source linkedin-browser --source indeed --max-workers 2

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  new-jobs --source linkedin-browser

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  new-jobs --source indeed

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  export-jobs --source linkedin-browser --out "$ROOT_DIR/reports/linkedin_jobs.csv"

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  export-jobs-html --source linkedin-browser --out "$ROOT_DIR/reports/linkedin_jobs.html" --title "LinkedIn Jobs"

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  export-jobs --source indeed --out "$ROOT_DIR/reports/indeed_jobs.csv"

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  export-jobs-html --source indeed --out "$ROOT_DIR/reports/indeed_jobs.html" --title "Indeed Jobs"

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  export-jobs --out "$ROOT_DIR/reports/all_jobs.csv"

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher \
  --config "$CONFIG" \
  export-jobs-html --out "$ROOT_DIR/reports/all_jobs.html" --title "All Jobs"

if command -v open >/dev/null 2>&1; then
  open "$ROOT_DIR/reports/all_jobs.html"
  open "$ROOT_DIR/reports/linkedin_jobs.html"
  open "$ROOT_DIR/reports/indeed_jobs.html"
else
  printf '%s\n' "Open combined report: $ROOT_DIR/reports/all_jobs.html"
  printf '%s\n' "Open LinkedIn report: $ROOT_DIR/reports/linkedin_jobs.html"
  printf '%s\n' "Open Indeed report: $ROOT_DIR/reports/indeed_jobs.html"
fi
