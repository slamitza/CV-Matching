# CV Job Matcher

CV Job Matcher scans configured job sources, scores postings against your CV, and keeps a local SQLite database of companies, jobs, and applications.

## What It Does

- Reads your CV text and extracts matching keywords.
- Scans enabled job sources on demand or from a daily scheduler.
- Stores companies and job postings in SQLite with deduplication.
- Scores every posting against your CV.
- Tracks jobs you applied to, including status and notes.
- Supports pluggable sources: public APIs, RSS feeds, and CSV imports.

LinkedIn and Indeed are intentionally not hard-coded as scrapers. Their public pages and terms change often, and automated scraping may violate site rules. Use official/approved integrations where available, saved search alerts, or CSV imports for those sites.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

cp config/settings.example.toml config/settings.toml
cp data/cv.example.txt data/cv.txt
```

Edit `data/cv.txt` with your CV content and adjust `config/settings.toml`.

```bash
job-matcher init-db
job-matcher scan
job-matcher jobs --min-score 35
job-matcher apply 1 --status applied --notes "Applied through company careers page"
job-matcher applications
```

Without installing the package, use:

```bash
PYTHONPATH=src python3 -m cv_job_matcher scan --config config/settings.example.toml
```

## Source Types

### Remotive

Uses Remotive's public remote-jobs endpoint.

```toml
[[sources]]
name = "remote-python"
type = "remotive"
enabled = true
search = "python"
category = "software-dev"
```

### RSS

Use this for job boards or company career pages that expose RSS/Atom feeds.

```toml
[[sources]]
name = "my-rss-feed"
type = "rss"
enabled = false
url = "https://example.com/jobs.rss"
default_company = "Unknown"
```

### CSV

Use CSV imports for LinkedIn, Indeed, or any other source where you maintain a saved/exported list.

```toml
[[sources]]
name = "manual-import"
type = "csv"
enabled = false
path = "data/manual_jobs.csv"
```

Expected CSV columns:

```csv
source_id,title,company,location,url,description,posted_at,remote
```

## Daily Scanning

See `docs/scheduling.md` for cron and macOS launchd examples. The repository includes `scripts/run_daily_scan.sh`, which runs one scan using `config/settings.toml`.

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
