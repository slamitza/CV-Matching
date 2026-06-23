#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
import argparse
import csv
import json
import re
import sqlite3
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
DEFAULT_OUT = ROOT_DIR / "data" / "manual_jobs.csv"
EXTRACTOR_JS = ROOT_DIR / "scripts" / "extract_linkedin_visible_jobs_json.js"
NEXT_PAGE_JS = ROOT_DIR / "scripts" / "linkedin_click_next_page.js"
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
    set nextJsPath to item 2 of argv
    set followNextPages to item 3 of argv
    set maxPages to item 4 of argv as integer
    set pageWait to item 5 of argv as real
    set jsText to read POSIX file jsPath
    set nextJsText to read POSIX file nextJsPath
    set delimiterText to "{TAB_DELIMITER}"
    set outputText to ""
    tell application "Google Chrome"
        repeat with windowIndex from 1 to count windows
            repeat with tabIndex from 1 to count tabs of window windowIndex
                set tabUrl to URL of tab tabIndex of window windowIndex
                if tabUrl contains "linkedin.com/jobs" then
                    set pageNumber to 1
                    repeat
                        try
                            tell tab tabIndex of window windowIndex
                                set jsResult to execute javascript jsText
                            end tell
                            set outputText to outputText & jsResult & linefeed & delimiterText & linefeed
                        on error errorMessage number errorNumber
                            set outputText to outputText & "{{\\"error\\":true,\\"message\\":\\"" & my jsonEscape(errorMessage) & "\\",\\"number\\":" & errorNumber & ",\\"url\\":\\"" & my jsonEscape(tabUrl) & "\\"}}" & linefeed & delimiterText & linefeed
                            exit repeat
                        end try

                        if followNextPages is not "1" then exit repeat
                        if pageNumber is greater than or equal to maxPages then exit repeat

                        try
                            tell tab tabIndex of window windowIndex
                                set nextResult to execute javascript nextJsText
                            end tell
                        on error
                            exit repeat
                        end try

                        if nextResult is not "clicked" then exit repeat
                        delay pageWait
                        set pageNumber to pageNumber + 1
                    end repeat
                end if
            end repeat
        end repeat
    end tell
    return outputText
end run
'''


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open LinkedIn searches in Chrome and save visible jobs to data/manual_jobs.csv."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Settings TOML path.")
    parser.add_argument("--source", default="linkedin-browser", help="LinkedIn source name.")
    parser.add_argument("--search", action="append", help="Open only this search term. Can be repeated.")
    parser.add_argument(
        "--existing-tabs",
        action="store_true",
        help="Do not open new tabs; extract from currently open Chrome LinkedIn tabs.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=15.0,
        help="Seconds to wait after opening tabs before extracting.",
    )
    parser.add_argument(
        "--follow-next-pages",
        action="store_true",
        help="Click LinkedIn's Next button in each open search tab until no next page is available.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Safety cap per LinkedIn tab when --follow-next-pages is used.",
    )
    parser.add_argument(
        "--page-wait",
        type=float,
        default=4.0,
        help="Seconds to wait after clicking LinkedIn's Next button.",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Destination manual jobs CSV.")
    args = parser.parse_args()
    source_config = _load_source_config(args.config, args.source)
    exclude_title_keywords = [
        str(keyword).lower()
        for keyword in source_config.get("exclude_title_keywords", [])
    ]
    easy_apply_only = bool(source_config.get("easy_apply_only", False))
    database_source_ids, database_urls = _load_database_seen_keys(args.config)
    if args.max_pages < 1:
        raise SystemExit("--max-pages must be at least 1")

    if not args.existing_tabs:
        urls = _configured_urls(args.config, args.source, args.search)
        for url in urls:
            print(f"Opening: {url}")
            subprocess.run(["open", "-a", "Google Chrome", url], check=False)
        if args.wait > 0:
            print(f"Waiting {args.wait:g}s for pages, login, and checks...")
            time.sleep(args.wait)

    results = _extract_open_linkedin_tabs(
        follow_next_pages=args.follow_next_pages,
        max_pages=args.max_pages,
        page_wait=args.page_wait,
    )
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
            "Some LinkedIn tabs still look logged out or security-gated. "
            "Handle them in Chrome, then rerun with --existing-tabs."
        )
    if args.follow_next_pages:
        print(f"Followed LinkedIn Next buttons with max-pages={args.max_pages}")

    imported, skipped, excluded = _merge_rows(
        _resolve_path(args.out),
        rows,
        exclude_title_keywords,
        database_source_ids,
        database_urls,
        easy_apply_only,
    )
    print(f"Imported {imported} jobs into {_resolve_path(args.out)}")
    if excluded:
        print(f"Excluded {excluded} rows by configured filters")
    if skipped:
        print(f"Skipped {skipped} duplicate or incomplete rows")
    return 0


def _configured_urls(config: str, source_name: str, search_terms: list[str] | None) -> list[str]:
    config_path = _resolve_config_path(config)
    settings = _load_toml(config_path)
    source = _find_source(settings, source_name)
    searches = search_terms or source.get("searches") or settings.get("search_terms") or []
    if not searches:
        raise SystemExit("No LinkedIn search terms found in config.")

    location = source.get("location")
    experience_levels = [str(level) for level in source.get("experience_levels", [])]
    easy_apply_only = bool(source.get("easy_apply_only", False))
    return [
        _linkedin_search_url(str(search), location, experience_levels, easy_apply_only)
        for search in searches
    ]


def _extract_open_linkedin_tabs(
    *,
    follow_next_pages: bool = False,
    max_pages: int = 1,
    page_wait: float = 4.0,
) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", encoding="utf-8", delete=False) as handle:
        handle.write(APPLE_SCRIPT)
        apple_script_path = handle.name

    completed = subprocess.run(
        [
            "osascript",
            apple_script_path,
            str(EXTRACTOR_JS),
            str(NEXT_PAGE_JS),
            "1" if follow_next_pages else "0",
            str(max_pages),
            str(page_wait),
        ],
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


def _merge_rows(
    out_path: Path,
    new_rows: list[dict],
    exclude_title_keywords: list[str] | None = None,
    database_source_ids: set[str] | None = None,
    database_urls: set[str] | None = None,
    easy_apply_only: bool = False,
) -> tuple[int, int, int]:
    existing_rows = _read_rows(out_path)
    seen_source_ids = {row["source_id"] for row in existing_rows if row.get("source_id")}
    seen_urls = {
        variant
        for row in existing_rows
        for variant in _url_variants(row.get("url"))
    }
    database_source_ids = database_source_ids or set()
    database_urls = database_urls or set()
    rows = list(existing_rows)
    imported = 0
    skipped = 0
    excluded = 0
    exclude_title_keywords = exclude_title_keywords or []

    for row in new_rows:
        normalized = {column: str(row.get(column) or "").strip() for column in COLUMNS}
        if not normalized["source_id"] or not normalized["title"] or not normalized["company"]:
            skipped += 1
            continue
        if _title_has_excluded_keyword(normalized["title"], exclude_title_keywords):
            excluded += 1
            continue
        if easy_apply_only and not _row_is_easy_apply(row):
            excluded += 1
            continue
        source_id = normalized["source_id"]
        url = normalized["url"]
        url_variants = _url_variants(url)
        if (
            source_id in seen_source_ids
            or source_id in database_source_ids
            or bool(url_variants & seen_urls)
            or bool(url_variants & database_urls)
        ):
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
    return imported, skipped, excluded


def _title_has_excluded_keyword(title: str, excluded_keywords: list[str]) -> bool:
    normalized_title = title.lower()
    return any(_keyword_matches_title(normalized_title, keyword) for keyword in excluded_keywords)


def _row_is_easy_apply(row: dict) -> bool:
    if str(row.get("easy_apply") or "").strip().lower() in {"1", "true", "yes"}:
        return True
    return bool(re.search(r"\beasy\s+apply\b", str(row.get("description") or ""), re.I))


def _keyword_matches_title(normalized_title: str, keyword: str) -> bool:
    normalized_keyword = keyword.strip().lower()
    if not normalized_keyword:
        return False
    if normalized_keyword == "intern":
        return bool(re.search(r"\bintern(?:s|ship)?\b", normalized_title))
    return normalized_keyword in normalized_title


def _url_variants(url: str | None) -> set[str]:
    value = str(url or "").strip()
    if not value:
        return set()
    variants = {value, value.rstrip("/")}
    if not value.endswith("/"):
        variants.add(f"{value}/")
    return variants


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


def _load_source_config(config: str, source_name: str) -> dict:
    config_path = _resolve_config_path(config)
    settings = _load_toml(config_path)
    return _find_source(settings, source_name)


def _load_database_seen_keys(config: str) -> tuple[set[str], set[str]]:
    config_path = _resolve_config_path(config)
    settings = _load_toml(config_path)
    database_path = _resolve_path(str(settings.get("database_path", "data/job_matcher.sqlite3")))
    if not database_path.exists():
        return set(), set()

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute("SELECT source_id, url FROM jobs").fetchall()
    source_ids = {str(row[0]) for row in rows if row[0]}
    urls = {variant for row in rows for variant in _url_variants(row[1])}
    return source_ids, urls


def _find_source(settings: dict, source_name: str) -> dict:
    for source in settings.get("sources", []):
        if source.get("name") == source_name:
            return source
    for source in settings.get("sources", []):
        if source.get("type") == "linkedin_browser":
            return source
    raise SystemExit(f"No LinkedIn source found for: {source_name}")


def _linkedin_search_url(
    query: str,
    location: object | None,
    experience_levels: list[str] | None = None,
    easy_apply_only: bool = False,
) -> str:
    params = {
        "keywords": query,
        "f_TPR": "r86400",
    }
    if location:
        params["location"] = str(location)
    if experience_levels:
        params["f_E"] = ",".join(str(level) for level in experience_levels)
    if easy_apply_only:
        params["f_AL"] = "true"
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


if __name__ == "__main__":
    raise SystemExit(main())
