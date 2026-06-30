# Scheduling Daily Scans

The scanner is designed to run once, then exit. Use your operating system scheduler to run it daily.

## macOS launchd

Create `~/Library/LaunchAgents/com.cv-job-matcher.daily.plist`.

Replace `/path/to/CV-Matching` with the absolute path to this project folder on your machine.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.cv-job-matcher.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/CV-Matching/scripts/run_daily_scan.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/CV-Matching</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/path/to/CV-Matching/reports/daily-scan.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/CV-Matching/reports/daily-scan.err</string>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.cv-job-matcher.daily.plist
```

## cron

Open your crontab:

```bash
crontab -e
```

Run daily at 08:00:

```cron
0 8 * * * /path/to/CV-Matching/scripts/run_daily_scan.sh >> /path/to/CV-Matching/reports/daily-scan.log 2>&1
```

## Notes

- Keep `config/settings.toml` and `data/cv.txt` local; they are ignored by git.
- Use CSV imports or approved APIs for job boards that do not allow automated scraping.
- For email job alerts, save or export the postings into `data/manual_jobs.csv` and enable the CSV source.
