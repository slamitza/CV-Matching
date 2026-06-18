#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
import argparse
import subprocess
import webbrowser

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "config" / "settings.toml"
EXAMPLE_CONFIG = ROOT_DIR / "config" / "settings.example.toml"
DEFAULT_BASE_URL = "https://ch.indeed.com/jobs"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open configured Indeed searches in your normal default browser."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Settings TOML path.",
    )
    parser.add_argument(
        "--source",
        default="indeed",
        help="Indeed source name to read from config.",
    )
    parser.add_argument(
        "--search",
        action="append",
        help="Open only this search term. Can be repeated.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="Number of Indeed results pages to open per search term.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print URLs without opening browser tabs.",
    )
    parser.add_argument(
        "--browser",
        choices=["default", "chrome", "safari"],
        default="default",
        help="Browser to open tabs in.",
    )
    args = parser.parse_args()

    config_path = _resolve_config_path(args.config)
    settings = _load_toml(config_path)
    source = _find_source(settings, args.source)
    searches = args.search or source.get("searches") or settings.get("search_terms") or []
    if not searches:
        raise SystemExit("No Indeed search terms found in config.")

    base_url = str(source.get("base_url", DEFAULT_BASE_URL)).rstrip("/")
    location = source.get("location")
    if args.pages < 1:
        raise SystemExit("--pages must be at least 1")

    urls = [
        _indeed_search_url(base_url, str(search), location, start=page_index * 10)
        for search in searches
        for page_index in range(args.pages)
    ]

    print(f"Using config: {config_path}")
    for url in urls:
        print(url)
        if not args.print_only:
            _open_url(url, args.browser)

    return 0


def _resolve_config_path(config: str) -> Path:
    path = Path(config).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    if path.exists():
        return path
    if path == DEFAULT_CONFIG and EXAMPLE_CONFIG.exists():
        return EXAMPLE_CONFIG
    raise SystemExit(f"Config not found: {path}")


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


def _indeed_search_url(
    base_url: str,
    query: str,
    location: object | None,
    *,
    start: int = 0,
) -> str:
    params = {
        "q": query,
        "fromage": "1",
        "sort": "date",
    }
    if location:
        params["l"] = str(location)
    if start > 0:
        params["start"] = str(start)
    return f"{base_url}?{urlencode(params)}"


def _open_url(url: str, browser: str) -> None:
    if browser == "chrome":
        subprocess.run(["open", "-a", "Google Chrome", url], check=False)
        return
    if browser == "safari":
        subprocess.run(["open", "-a", "Safari", url], check=False)
        return
    webbrowser.open_new_tab(url)


if __name__ == "__main__":
    raise SystemExit(main())
