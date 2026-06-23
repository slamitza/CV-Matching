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
3. Review each LinkedIn tab manually.
4. Do not click Next or close tabs until after you save this page from Terminal.

In this Terminal:
- Press 1 to save jobs from all currently open LinkedIn tabs, then keep reviewing.
- After pressing 1, go back to Chrome, click Next on tabs that have another page,
  and close tabs that are done.
- Press 0 to save one final time, import jobs into the database, and print new jobs.

EOF

while :; do
  printf '%s' "Press 1 to save current LinkedIn tabs, or 0 to finish/import: "
  IFS= read -r choice

  case "$choice" in
    1)
      "$ROOT_DIR/scripts/save_linkedin_from_chrome.sh" --existing-tabs
      printf '%s\n' ""
      printf '%s\n' "Saved current LinkedIn tabs. In Chrome, click Next on tabs that have another page, close tabs that are done, then come back here."
      ;;
    0)
      "$ROOT_DIR/scripts/save_linkedin_from_chrome.sh" --existing-tabs
      break
      ;;
    *)
      printf '%s\n' "Type 1 or 0."
      ;;
  esac
done

PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher scan --source manual-csv
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher new-jobs --source manual-csv
PYTHONPATH="$ROOT_DIR/src" "$PYTHON" -m cv_job_matcher export-jobs-html --out "$ROOT_DIR/reports/jobs.html" --title "All Jobs"
"$ROOT_DIR/scripts/open_jobs_dashboard.sh"
