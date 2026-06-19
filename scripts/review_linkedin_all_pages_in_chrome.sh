#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

"$ROOT_DIR/scripts/open_linkedin_searches.sh" --browser chrome "$@"

cat <<'EOF'

Chrome LinkedIn tabs are open.

In Chrome:
1. Log in or handle security checks if LinkedIn asks.
2. Wait until each LinkedIn page has job cards.
3. Leave each tab on page 1 of its search.
4. Come back here and press Enter.

This command will save page 1, click LinkedIn's Next button in each tab,
save the next page, and stop when Next is unavailable or disabled.

EOF

printf '%s' "Press Enter when the Chrome tabs are ready..."
IFS= read -r _

"$ROOT_DIR/scripts/save_linkedin_from_chrome.sh" --existing-tabs --follow-next-pages
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher scan --source manual-csv
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher new-jobs --source manual-csv
