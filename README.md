# CV Job Matcher

CV Job Matcher scans configured job sources and keeps a local SQLite database of companies, job postings, and applications.

## What It Does

- Scans enabled job sources on demand or from a daily scheduler.
- Stores companies and job postings in SQLite with deduplication.
- Tracks posting IDs, job title, company, URL, first seen, last seen, and how often a posting was seen.
- Tracks jobs you applied to, including status and notes.
- Supports pluggable sources: public APIs, RSS feeds, CSV imports, and browser-assisted searches.
- Optional: score postings against your CV when `score_jobs = true`.

LinkedIn and Indeed are intentionally not hard-coded as scrapers. Their public pages and terms change often, and automated scraping may violate site rules. Use official/approved integrations where available, saved search alerts, or CSV imports for those sites.

## Recommended Source Mix

The most robust long-term setup is not only browser automation. Use several low-risk sources together:

- LinkedIn browser-assisted searches for targeted review.
- Job alerts from LinkedIn and niche boards, imported into `data/manual_jobs.csv`.
- Company career pages for employers you care about.
- RSS/Atom feeds where job boards or career pages provide them.
- Public or approved APIs where available.
- CSV/manual imports for anything that should not be scraped directly.

This makes the daily scan less dependent on one website, reduces account-risk from repetitive browsing, and gives you a backup path when LinkedIn asks for MFA, CAPTCHA, or changes its layout.

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
job-matcher new-jobs
job-matcher jobs
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

Start from [data/manual_jobs.example.csv](/Users/slamitza/Documents/CV-Matching/data/manual_jobs.example.csv), then create your private `data/manual_jobs.csv`.

## Daily Scanning

See `docs/scheduling.md` for cron and macOS launchd examples. The repository includes `scripts/run_daily_scan.sh`, which runs one scan using `config/settings.toml`.

## LinkedIn Browser Profile

For interactive LinkedIn setup, use a dedicated Playwright browser profile:

```bash
python -m playwright install chromium
scripts/open_linkedin_profile.sh
```

This opens LinkedIn in a clean browser profile stored at `data/browser-profiles/linkedin-job-search/`. Log in manually with the email account you choose. The profile folder is ignored by git and keeps LinkedIn cookies/session data for later browser-assisted searches.

Do not store LinkedIn passwords in this repository or in config files.

For browser-assisted searches, keep the pace conservative: visible browser, reusable profile, small configured searches, pauses between actions, slow scrolling, and stop immediately if LinkedIn shows MFA, CAPTCHA, or unusual security prompts.

The LinkedIn browser source is disabled by default in `config/settings.example.toml`. It is configured for:

- Data Science
- Bioinformatics
- AI engineer
- ML engineer
- Data Scientist
- Biostatistic
- Biostatistician
- Research Engineer

It also excludes job titles containing:

- writer
- director
- executive
- junior

The pacing profile is intentionally slow and visible:

- Open LinkedIn feed first.
- Scroll a few feed posts and pause as if reading.
- Wait roughly 2-3 seconds plus random jitter before job search.
- Type each search term with per-key delays.
- Wait roughly 2-3 seconds plus random jitter before filters.
- Apply "Past 24 hours" when available, otherwise use LinkedIn's 24-hour search URL parameter.
- Scroll results slowly and keep collecting each newly loaded job card until no new cards appear for several rounds or the safety cap is reached.
- Move to the next LinkedIn results page and repeat until LinkedIn has no next page.
- Skip excluded titles such as jobs containing "writer", "director", "executive", or "junior".
- Collect visible listings only.
- Pause between searches.

After copying `config/settings.example.toml` to `config/settings.toml`, run only this source with:

```bash
scripts/scan_linkedin_jobs.sh
```

This stores collected jobs in the same SQLite database with deduplication, then prints the fresh non-duplicate jobs from that scan. It never applies to jobs.

The primary output fields are:

- Website
- JobID
- Job title
- Company
- URL

The jobs table keeps the LinkedIn posting number as `source_id`, plus title, company, URL, `first_seen_at`, `last_seen_at`, and `seen_count`. This lets you collect just-posted URLs while avoiding duplicates from previous scans.

After any scan, show only new non-duplicate jobs from the latest successful LinkedIn scan:

```bash
job-matcher new-jobs --source linkedin-browser
```

Export all saved LinkedIn jobs to CSV:

```bash
job-matcher export-jobs --source linkedin-browser --out reports/linkedin_jobs.csv
```

CV scoring is off by default. If you later want keyword scoring in addition to tracking, set `score_jobs = true` in `config/settings.toml`.

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
