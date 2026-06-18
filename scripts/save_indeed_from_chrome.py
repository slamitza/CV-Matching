#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
import argparse
import csv
import json
import subprocess
import tempfile
import time

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "config" / "settings.toml"
EXAMPLE_CONFIG = ROOT_DIR / "config" / "settings.example.toml"
DEFAULT_BASE_URL = "https://ch.indeed.com/jobs"
DEFAULT_OUT = ROOT_DIR / "data" / "manual_jobs.csv"
EXTRACTOR_JS = ROOT_DIR / "scripts" / "extract_indeed_visible_jobs_json.js"
TAB_DELIMITER = "<<<CV_MATCHING_TAB>>>"
COLUMNS = [
    "source_id",
    "title",
    "company",
    "location",
    "url",
    "description",
    "posted_at",
    "remote",
]

APPLE_SCRIPT = f'''
on jsonEscape(inputText)
    set inputText to inputText as text
    set AppleScript's text item delimiters to "\\\\"
    set textItems to text items of inputText
    set AppleScript's text item delimiters to "\\\\\\\\"
    set inputText to textItems as text
    set AppleScript's text item delimiters to "\\""
    set textItems to text items of inputText
    set AppleScript's text item delimiters to "\\\\\\""
    set inputText to textItems as text
    set AppleScript's text item delimiters to ""
    return inputText
end jsonEscape

on run argv
    set jsPath to item 1 of argv
    set jsText to read POSIX file jsPath
    set delimiterText to "{TAB_DELIMITER}"
    set outputText to ""
    tell application "Google Chrome"
        repeat with windowIndex from 1 to count windows
            repeat with tabIndex from 1 to count tabs of window windowIndex
                set tabUrl to URL of tab tabIndex of window windowIndex
                if tabUrl contains "indeed." then
                    try
                        tell tab tabIndex of window windowIndex
                            set jsResult to execute javascript jsText
                        end tell
                        set outputText to outputText & jsResult & linefeed & delimiterText & linefeed
                    on error errorMessage number errorNumber
                        set outputText to outputText & "{{\\"error\\":true,\\"message\\":\\"" & my jsonEscape(errorMessage) & "\\",\\"number\\":" & errorNumber & ",\\"url\\":\\"" & my jsonEscape(tabUrl) & "\\"}}" & linefeed & delimiterText & linefeed
                    end try
                end if
            end repeat
        end repeat
    end tell
    return outputText
end run
'''


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open Indeed searches in Chrome and save visible jobs to data/manual_jobs.csv."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Settings TOML path.")
    parser.add_argument("--source", default="indeed", help="Indeed source name to read from config.")
    parser.add_argument("--search", action="append", help="Open only this search term. Can be repeated.")
    parser.add_argument(
        "--existing-tabs",
        action="store_true",
        help="Do not open new tabs; extract from currently open Chrome Indeed tabs.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=15.0,
        help="Seconds to wait after opening tabs before extracting.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Destination manual jobs CSV.")
    args = parser.parse_args()

    if not args.existing_tabs:
        urls = _configured_urls(args.config, args.source, args.search)
        for url in urls:
            print(f"Opening: {url}")
            subprocess.run(["open", "-a", "Google Chrome", url], check=False)
        if args.wait > 0:
            print(f"Waiting {args.wait:g}s for pages and human checks...")
            time.sleep(args.wait)

    results = _extract_open_indeed_tabs()
    rows = []
    blocked_tabs = 0
    for result in results:
        if result.get("error"):
            message = result.get("message") or "unknown error"
            number = result.get("number")
            suffix = f" ({number})" if number is not None else ""
            print(f"Chrome tab error{suffix}: {message}")
            print(f"  {result.get('url', '')}")
            continue
        tab_rows = result.get("rows") or []
        rows.extend(tab_rows)
        if result.get("blocked"):
            blocked_tabs += 1
        print(f"{len(tab_rows):>3} jobs: {result.get('url', '')}")

    if blocked_tabs:
        print(
            "Some tabs still show Cloudflare/verification. Complete them in Chrome, "
            "then rerun with --existing-tabs."
        )

    imported, skipped = _merge_rows(_resolve_path(args.out), rows)
    print(f"Imported {imported} jobs into {_resolve_path(args.out)}")
    if skipped:
        print(f"Skipped {skipped} duplicate or incomplete rows")
    return 0


def _configured_urls(config: str, source_name: str, search_terms: list[str] | None) -> list[str]:
    config_path = _resolve_config_path(config)
    settings = _load_toml(config_path)
    source = _find_source(settings, source_name)
    searches = search_terms or source.get("searches") or settings.get("search_terms") or []
    if not searches:
        raise SystemExit("No Indeed search terms found in config.")

    base_url = str(source.get("base_url", DEFAULT_BASE_URL)).rstrip("/")
    location = source.get("location")
    return [_indeed_search_url(base_url, str(search), location) for search in searches]


def _extract_open_indeed_tabs() -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", encoding="utf-8", delete=False) as handle:
        handle.write(APPLE_SCRIPT)
        apple_script_path = handle.name

    completed = subprocess.run(
        ["osascript", apple_script_path, str(EXTRACTOR_JS)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(
            "Could not control Chrome through AppleScript.\n"
            "In Chrome, enable: View > Developer > Allow JavaScript from Apple Events.\n"
            f"{message}"
        )

    results = []
    for part in completed.stdout.split(TAB_DELIMITER):
        payload = part.strip()
        if not payload:
            continue
        try:
            results.append(json.loads(payload))
        except json.JSONDecodeError:
            results.append({"error": True, "url": "", "message": payload})
    return results


def _merge_rows(out_path: Path, new_rows: list[dict]) -> tuple[int, int]:
    existing_rows = _read_rows(out_path)
    seen_source_ids = {row["source_id"] for row in existing_rows if row.get("source_id")}
    seen_urls = {row["url"] for row in existing_rows if row.get("url")}
    rows = list(existing_rows)
    imported = 0
    skipped = 0

    for row in new_rows:
        normalized = {column: str(row.get(column) or "").strip() for column in COLUMNS}
        if not normalized["source_id"] or not normalized["title"] or not normalized["company"]:
            skipped += 1
            continue
        source_id = normalized["source_id"]
        url = normalized["url"]
        if source_id in seen_source_ids or (url and url in seen_urls):
            skipped += 1
            continue
        rows.append(normalized)
        seen_source_ids.add(source_id)
        if url:
            seen_urls.add(url)
        imported += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return imported, skipped


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _resolve_config_path(config: str) -> Path:
    path = _resolve_path(config)
    if path.exists():
        return path
    if path == DEFAULT_CONFIG and EXAMPLE_CONFIG.exists():
        return EXAMPLE_CONFIG
    raise SystemExit(f"Config not found: {path}")


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _find_source(settings: dict, source_name: str) -> dict:
    for source in settings.get("sources", []):
        if source.get("name") == source_name:
            return source
    for source in settings.get("sources", []):
        if source.get("type") == "indeed_browser":
            return source
    raise SystemExit(f"No Indeed source found for: {source_name}")


def _indeed_search_url(base_url: str, query: str, location: object | None) -> str:
    params = {
        "q": query,
        "fromage": "1",
        "sort": "date",
    }
    if location:
        params["l"] = str(location)
    return f"{base_url}?{urlencode(params)}"


if __name__ == "__main__":
    raise SystemExit(main())
