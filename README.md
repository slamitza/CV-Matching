# CV Job Matcher

CV Job Matcher keeps a local SQLite database of job postings, companies, scans, and applications. It can scan configured sources, import manually collected jobs, deduplicate repeated postings, and track which jobs you applied to.

LinkedIn and Indeed collection is done through your normal Chrome browser plus manual CSV import. Controlled Chromium/Patchright automation has been removed because these sites detect it too easily.

## For The Person Receiving This Folder

This copy is meant for LinkedIn and Indeed job tracking only. The browser scripts open LinkedIn and Indeed searches in normal Google Chrome, save the visible jobs, import them into the local SQLite database, and show them in the local dashboard.

If this folder was shared with existing job data, it may already include the original user's current searches, excluded companies, banned words, saved jobs, reports, and application/discard status. Review the configuration before running new searches.

## Reset Or Change The Job Search

Main settings live in:

```text
config/settings.toml
```

If that file is missing, create it from the example:

```bash
cp config/settings.example.toml config/settings.toml
```

To change the jobs being searched, edit these lists:

```toml
search_terms = [
  "Data Science",
  "Bioinformatics",
  "AI engineer"
]

[chrome.linkedin]
searches = [
  "Data Science",
  "Bioinformatics",
  "AI engineer"
]

[chrome.indeed]
searches = [
  "Data Science",
  "Bioinformatics",
  "AI engineer"
]
```

Keep the same job names in all three places unless you intentionally want different behavior. `search_terms` is the general project list. `[chrome.linkedin].searches` controls LinkedIn Chrome searches. `[chrome.indeed].searches` controls Indeed Chrome searches.

To change the country/city:

```toml
[chrome.linkedin]
location = "Switzerland"

[chrome.indeed]
location = "Switzerland"
```

To ban companies, add company name fragments here:

```toml
excluded_companies = [
  "Example Company",
  "Another Company"
]
```

Matching is case-insensitive and uses fragments, so `google` will match `Google`, `Google Switzerland`, and similar names.

To ban words or phrases in job titles, edit both LinkedIn and Indeed lists:

```toml
[chrome.linkedin]
exclude_title_keywords = [
  "writer",
  "director",
  "executive",
  "junior",
  "doctoral",
  "trainee",
  "intern",
  "internship",
  "head of",
  "linux"
]

[chrome.indeed]
exclude_title_keywords = [
  "writer",
  "director",
  "executive",
  "junior",
  "doctoral",
  "trainee",
  "intern",
  "internship",
  "head of",
  "linux"
]
```

These are the banned words/phrases used when saving visible jobs from LinkedIn and Indeed. Matching is case-insensitive.

LinkedIn has two extra optional filters:

```toml
[chrome.linkedin]
easy_apply_only = false
experience_levels = []
```

Set `easy_apply_only = true` to keep only LinkedIn jobs marked Easy Apply. Use `experience_levels` only if you want LinkedIn's experience-level URL filters.

## Reset Saved Jobs

The saved jobs and application/discard status are stored in:

```text
data/job_matcher.sqlite3
```

To start fresh, delete the SQLite database and initialize it again:

```bash
rm data/job_matcher.sqlite3
job-matcher init-db
```

If you use the non-installed command style:

```bash
rm data/job_matcher.sqlite3
PYTHONPATH=src .venv/bin/python -m cv_job_matcher init-db
```

Manual browser imports are collected in:

```text
data/manual_jobs.csv
```

To clear manually collected LinkedIn/Indeed jobs, either delete that file or recreate it from the example:

```bash
cp data/manual_jobs.example.csv data/manual_jobs.csv
```

## Setup

```bash
cd /Users/slamitza/Documents/CV-Matching
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
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

For the interactive Open/Applied/Discarded dashboard:

```bash
job-matcher serve-jobs
```

Open `http://127.0.0.1:8765/`. Click `Applied` to move a job from Open Jobs to the Applied page, or `Discard` to move it to the Discarded page. The change is stored in SQLite, so future scans still recognize applied and discarded jobs as already known and keep them out of the open-jobs page.

Export a browser-readable report:

```bash
job-matcher export-jobs-html --out reports/jobs.html --title "Jobs"
open reports/jobs.html
```

## Indeed In Chrome

Use this to collect Indeed jobs in your normal Chrome browser.

First enable this Chrome setting once:

```text
View > Developer > Allow JavaScript from Apple Events
```

Then run:

```bash
./scripts/review_indeed_in_chrome.sh
```

The script opens pages 1 through 3 for each configured Indeed search in Google Chrome and waits for your confirmation:

- In Chrome, pass Cloudflare if it appears, wait for job cards, and review the opened pages.
- Return to Terminal and press `1`.
- The script saves visible jobs from all currently open Indeed tabs.
- It closes only Indeed tabs after saving.
- It imports `data/manual_jobs.csv`, prints newly added jobs, regenerates `reports/jobs.html`, and opens the dashboard.

The save step:

- Reads visible jobs from open Indeed tabs.
- Merges them into `data/manual_jobs.csv`.

If the tabs are already open and you only want to save the current visible jobs:

```bash
./scripts/save_indeed_from_chrome.sh --existing-tabs
PYTHONPATH=src .venv/bin/python -m cv_job_matcher scan --source manual-csv
PYTHONPATH=src .venv/bin/python -m cv_job_matcher new-jobs --source manual-csv
```

To also close Indeed tabs after saving:

```bash
./scripts/save_indeed_from_chrome.sh --existing-tabs --close-tabs
```

To let normal Chrome walk through every available page for one search, with a safety cap:

```bash
./scripts/save_indeed_from_chrome.sh --search "Data Science" --follow-next-pages --max-pages 25
PYTHONPATH=src .venv/bin/python -m cv_job_matcher scan --source manual-csv
PYTHONPATH=src .venv/bin/python -m cv_job_matcher new-jobs --source manual-csv
```

This opens page 1 in Google Chrome, saves visible jobs, clicks Next in the same tab, and stops when there are no visible jobs, no Next button, a verification page, or the page cap is reached.

To open more Indeed result pages per search term:

```bash
./scripts/review_indeed_in_chrome.sh --pages 5
```

The default is 3 pages per search term. `--pages 5` opens pages 1 through 5 for every search term, which can create many tabs. Duplicate jobs are skipped during import.

To run one search only:

```bash
./scripts/review_indeed_in_chrome.sh --search "Data Science"
```

## LinkedIn

Use the normal Chrome review flow:

```bash
./scripts/review_linkedin_in_chrome.sh
```

The script opens pages 1 through 3 for each configured LinkedIn search in Google Chrome and waits. In Chrome, log in or handle security checks if LinkedIn asks, wait for job cards, and review the pages. Return to Terminal and press `1` to save visible jobs, close LinkedIn job tabs, import them into SQLite, print the new jobs, regenerate `reports/jobs.html`, and open the dashboard.

To run one job name, still with pages 1 through 3 by default:

```bash
./scripts/review_linkedin_in_chrome.sh --search "Data Science"
```

LinkedIn search URLs can optionally include experience-level filters from `config/settings.toml`, but this is disabled by default so jobs without a classified level are not filtered out. To enable Associate and Mid-Senior level only, add:

```toml
experience_levels = [3, 4] # Associate, Mid-Senior level
```

LinkedIn can also be restricted to Easy Apply jobs:

```toml
easy_apply_only = true
```

When enabled, the Chrome workflow opens LinkedIn URLs with the Easy Apply filter and skips visible LinkedIn cards that do not show `Easy Apply`.

If LinkedIn tabs are already open and ready, extract only from existing tabs:

```bash
./scripts/save_linkedin_from_chrome.sh --existing-tabs
PYTHONPATH=src .venv/bin/python -m cv_job_matcher scan --source manual-csv
PYTHONPATH=src .venv/bin/python -m cv_job_matcher new-jobs --source manual-csv
```

To also close LinkedIn job tabs after saving:

```bash
./scripts/save_linkedin_from_chrome.sh --existing-tabs --close-tabs
```

To let normal Chrome walk through every available page for one search, with a safety cap:

```bash
./scripts/save_linkedin_from_chrome.sh --search "Data Science" --follow-next-pages --max-pages 25
PYTHONPATH=src .venv/bin/python -m cv_job_matcher scan --source manual-csv
PYTHONPATH=src .venv/bin/python -m cv_job_matcher new-jobs --source manual-csv
```

This uses Google Chrome, not controlled Chromium. It saves page 1, clicks Next in the same tab, and stops when there are no visible jobs, no Next button, a security-gated page, or the page cap is reached.

To override the number of LinkedIn result pages per search term:

```bash
./scripts/review_linkedin_in_chrome.sh --pages 3
```

The default is 3 pages per search term. LinkedIn pages use `start=25`, `start=50`, and so on.

To save every available LinkedIn results page without choosing a fixed page count, use the manual page-review workflow:

```bash
./scripts/review_linkedin_all_pages_in_chrome.sh
```

This opens page 1 for each configured search, waits for you to log in or handle checks, then gives you a loop:

- Press `1` to save jobs from all currently open LinkedIn tabs and keep reviewing.
- After pressing `1`, go back to Chrome, click Next manually on tabs that have another page, and close tabs that are done.
- Press `0` when you are on the last useful page or all tabs are closed. The script saves one final time, imports `data/manual_jobs.csv`, and prints newly added jobs.
- After importing, it regenerates `reports/jobs.html` and opens the interactive jobs dashboard.

If the LinkedIn tabs are already open and you only want to save the current visible jobs:

```bash
./scripts/save_linkedin_from_chrome.sh --existing-tabs
PYTHONPATH=src .venv/bin/python -m cv_job_matcher scan --source manual-csv
PYTHONPATH=src .venv/bin/python -m cv_job_matcher new-jobs --source manual-csv
```

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

Open the persistent dashboard:

```bash
job-matcher serve-jobs
```

The static HTML reports are useful for viewing/exporting. The local dashboard is the place to click `Applied` or `Discard`, because it writes that status back to SQLite.

Reports, the dashboard, and `job-matcher jobs` list jobs first seen in the latest successful scan at the top, then fall back to the normal company/title ordering.

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
- `search_terms`: shared search terms for sources and Chrome review helpers.
- `excluded_companies`: case-insensitive company name fragments to skip during imports and scans.
- `sources`: source-specific settings.
- `[chrome.linkedin]` and `[chrome.indeed]`: normal Chrome review settings for job-board searches.
- `exclude_title_keywords`: title phrases to skip in Chrome visible-tab saves and manual CSV imports.
- `easy_apply_only`: LinkedIn-only setting to keep only jobs labeled `Easy Apply`.

Private files such as `config/settings.toml`, `data/cv.txt`, generated reports, and the SQLite database should stay out of git unless you intentionally want to publish them.

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
