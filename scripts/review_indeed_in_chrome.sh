#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

"$ROOT_DIR/scripts/open_indeed_searches.sh" --browser chrome "$@"

cat <<'EOF'

Chrome tabs are open.

In Chrome:
1. Pass Cloudflare if it appears.
2. Wait until each Indeed page has job cards.
3. Scroll each search page until the jobs you want are loaded.
4. Come back here and press Enter.

EOF

printf '%s' "Press Enter when the Chrome tabs are ready..."
IFS= read -r _

"$ROOT_DIR/scripts/save_indeed_from_chrome.sh" --existing-tabs
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher scan --source manual-csv
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher new-jobs --source manual-csv
