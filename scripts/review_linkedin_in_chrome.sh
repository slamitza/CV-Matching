#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

HAS_PAGES=0
for arg in "$@"; do
  case "$arg" in
    --pages|--pages=*)
      HAS_PAGES=1
      ;;
  esac
done

if [ "$HAS_PAGES" -eq 0 ]; then
  set -- --pages 3 "$@"
fi

"$ROOT_DIR/scripts/open_linkedin_searches.sh" --browser chrome "$@"

cat <<'EOF'

Chrome LinkedIn tabs are open.

In Chrome:
1. Log in or handle security checks if LinkedIn asks.
2. Wait until each LinkedIn page has job cards.
3. Review the opened pages. By default this opens pages 1 through 3 per search.
4. Come back here and press 1 to save/import all visible jobs.

In this Terminal:
- Press 1 to save visible jobs from all currently open LinkedIn job tabs.
- After saving, the script closes only LinkedIn job tabs, imports jobs into the
  database, prints new jobs, regenerates the report, and opens the dashboard.

EOF

while :; do
  printf '%s' "Press 1 when the Chrome tabs are ready to save/import: "
  IFS= read -r choice
  case "$choice" in
    1)
      break
      ;;
    *)
      printf '%s\n' "Type 1 when ready."
      ;;
  esac
done

"$ROOT_DIR/scripts/save_linkedin_from_chrome.sh" --existing-tabs --close-tabs
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher scan --source manual-csv
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher new-jobs --source manual-csv
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher export-jobs-html --out "$ROOT_DIR/reports/jobs.html" --title "All Jobs"
"$ROOT_DIR/scripts/open_jobs_dashboard.sh"
