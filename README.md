# CV Job Matcher

CV Job Matcher keeps a local SQLite database of job postings, companies, scans, and applications. It can scan configured sources, import manually collected jobs, deduplicate repeated postings, and track which jobs you applied to.

LinkedIn and Indeed browser-assisted flows are intentionally conservative and visible. Their public pages and anti-abuse checks change often, so this repo also supports manual CSV import and normal-browser review flows.

## Setup

```bash
cd /Users/slamitza/Documents/CV-Matching
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
patchright install chromium
cp config/settings.example.toml config/settings.toml
cp data/cv.example.txt data/cv.txt
```

Edit:

- `config/settings.toml` for search terms, sources, location, and scoring.
- `data/cv.txt` if you enable `score_jobs = true`.

Initialize the database:

```bash
job-matcher init-db
```

Without installing the console command, use:

```bash
PYTHONPATH=src .venv/bin/python -m cv_job_matcher init-db
```

## Main Commands

Scan enabled sources:

```bash
job-matcher scan
```

Show new jobs from the latest successful scan:

```bash
job-matcher new-jobs
```

List saved jobs with internal IDs:

```bash
job-matcher jobs --limit 100
```

Mark a job as applied. Use the numeric `ID` from `job-matcher jobs`, not the Indeed or LinkedIn posting ID:

```bash
job-matcher apply 123 --status applied --notes "Applied on Indeed"
job-matcher applications
```

Export a browser-readable report:

```bash
job-matcher export-jobs-html --out reports/jobs.html --title "Jobs"
open reports/jobs.html
```

## Indeed In Chrome

Use this when Indeed works in your normal Chrome browser but the automation profile gets stuck on Cloudflare.

First enable this Chrome setting once:

```text
View > Developer > Allow JavaScript from Apple Events
```

Then run:

```bash
./scripts/review_indeed_in_chrome.sh
```

The script opens all configured Indeed searches in Google Chrome and waits. In Chrome, pass Cloudflare if it appears, wait for job cards, and scroll until the jobs you want are loaded. Return to Terminal and press Enter.

The script then:

- Reads visible jobs from open Indeed tabs.
- Merges them into `data/manual_jobs.csv`.
- Imports them through the `manual-csv` source.
- Prints only newly added jobs.

If the tabs are already open and ready, run only the save/import steps:

```bash
./scripts/save_indeed_from_chrome.sh --existing-tabs
PYTHONPATH=src .venv/bin/python -m cv_job_matcher scan --source manual-csv
PYTHONPATH=src .venv/bin/python -m cv_job_matcher new-jobs --source manual-csv
```

To open more Indeed result pages per search term:

```bash
./scripts/review_indeed_in_chrome.sh --pages 2
```

Start with the default one page. `--pages 2` opens page 1 and page 2 for every search term, which can create many tabs. Duplicate jobs are skipped during import.

To run one search only:

```bash
./scripts/review_indeed_in_chrome.sh --search "Data Science"
```

## Indeed Automation Profile

The dedicated Indeed browser source opens a visible Chromium profile at:

```text
data/browser-profiles/indeed-job-search/
```

Run the direct Indeed scan:

```bash
./scripts/scan_indeed_jobs.sh
```

If Indeed shows a CAPTCHA, cookie prompt, security prompt, or sign-in prompt inside that profile:

```bash
./scripts/open_indeed_profile.sh
```

Handle the prompt manually, close the browser, then rerun the scan. If Cloudflare still loops in the automation profile, use the Chrome flow above instead.

## LinkedIn

Open the dedicated LinkedIn profile and log in manually:

```bash
./scripts/open_linkedin_profile.sh
```

Run the LinkedIn browser-assisted scan:

```bash
./scripts/scan_linkedin_jobs.sh
```

Run LinkedIn and Indeed browser-assisted scans in parallel:

```bash
./scripts/scan_linkedin_indeed_parallel.sh
```

These flows are visible and paced conservatively. Stop if a site asks for MFA, CAPTCHA, or unusual verification.

## Manual CSV Import

Manual imports use:

```text
data/manual_jobs.csv
```

Expected columns:

```csv
source_id,title,company,location,url,description,posted_at,remote
```

Create the file from the example if needed:

```bash
cp data/manual_jobs.example.csv data/manual_jobs.csv
```

Enable the `manual-csv` source in `config/settings.toml`, then import:

```bash
PYTHONPATH=src .venv/bin/python -m cv_job_matcher scan --source manual-csv
```

If you downloaded a CSV from the browser extractor, merge it into the manual CSV:

```bash
./scripts/import_manual_jobs_csv.sh ~/Downloads/indeed-visible-jobs-2026-06-18.csv
```

## Reports

Export CSV:

```bash
job-matcher export-jobs --out reports/jobs.csv
job-matcher export-jobs --source manual-csv --out reports/manual_jobs.csv
```

Export HTML:

```bash
job-matcher export-jobs-html --out reports/jobs.html --title "Jobs"
job-matcher export-jobs-html --source manual-csv --out reports/manual_jobs.html --title "Manual / Indeed Jobs"
```

Open the report:

```bash
open reports/manual_jobs.html
```

## What New And Updated Mean

Scan output looks like:

```text
manual-csv: found=55 new=6 updated=49 ok
```

- `found`: rows read from the source during this scan.
- `new`: postings not previously saved in the database.
- `updated`: postings already saved and seen again.

An update refreshes job fields such as title, company, location, URL, description, `last_seen_at`, and `seen_count`. It does not delete application records, and it does not overwrite a job status such as `applied`.

## Configuration

Important config fields in `config/settings.toml`:

- `database_path`: SQLite database location.
- `score_jobs`: set `true` to score jobs against `data/cv.txt`.
- `search_terms`: shared search terms for browser-assisted sources.
- `sources`: source-specific settings.
- `exclude_title_keywords`: words to skip in browser-assisted scans.
- `max_results_per_search` and `max_pages_per_search`: optional safety caps.

Private files such as `config/settings.toml`, `data/cv.txt`, browser profiles, generated reports, and the SQLite database should stay out of git unless you intentionally want to publish them.

## Development

Run tests:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Useful local checks:

```bash
PYTHONPATH=src .venv/bin/python -m cv_job_matcher --help
PYTHONPATH=src .venv/bin/python -m cv_job_matcher jobs --limit 5
```
