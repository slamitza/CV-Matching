#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PORT="${JOBS_DASHBOARD_PORT:-8765}"
URL="http://127.0.0.1:$PORT/"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

if "$PYTHON" - "$PORT" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as sock:
    sock.settimeout(0.25)
    sys.exit(0 if sock.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
then
  :
else
  mkdir -p "$ROOT_DIR/reports"
  nohup env PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher serve-jobs --port "$PORT" > "$ROOT_DIR/reports/jobs_dashboard.log" 2>&1 &
  sleep 1
  if "$PYTHON" - "$PORT" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as sock:
    sock.settimeout(0.25)
    sys.exit(0 if sock.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
  then
    :
  else
    printf '%s\n' "Dashboard did not start. Last log lines:"
    tail -20 "$ROOT_DIR/reports/jobs_dashboard.log" || true
    exit 1
  fi
fi

open "$URL" || printf '%s\n' "Open dashboard: $URL"
