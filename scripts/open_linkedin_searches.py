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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open configured LinkedIn searches in your normal browser."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Settings TOML path.")
    parser.add_argument("--source", default="linkedin-browser", help="LinkedIn source name.")
    parser.add_argument("--search", action="append", help="Open only this search term. Can be repeated.")
    parser.add_argument("--pages", type=int, default=1, help="Number of result pages per search term.")
    parser.add_argument("--print-only", action="store_true", help="Print URLs without opening tabs.")
    parser.add_argument(
        "--browser",
        choices=["default", "chrome", "safari"],
        default="default",
        help="Browser to open tabs in.",
    )
    args = parser.parse_args()

    if args.pages < 1:
        raise SystemExit("--pages must be at least 1")

    config_path = _resolve_config_path(args.config)
    settings = _load_toml(config_path)
    source = _find_source(settings, args.source)
    searches = args.search or source.get("searches") or settings.get("search_terms") or []
    if not searches:
        raise SystemExit("No LinkedIn search terms found in config.")

    location = source.get("location")
    experience_levels = [str(level) for level in source.get("experience_levels", [])]
    urls = [
        _linkedin_search_url(
            str(search),
            location,
            experience_levels,
            start=page_index * 25,
        )
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
        if source.get("type") == "linkedin_browser":
            return source
    raise SystemExit(f"No LinkedIn source found for: {source_name}")


def _linkedin_search_url(
    query: str,
    location: object | None,
    experience_levels: list[str] | None = None,
    *,
    start: int = 0,
) -> str:
    params = {
        "keywords": query,
        "f_TPR": "r86400",
    }
    if location:
        params["location"] = str(location)
    if experience_levels:
        params["f_E"] = ",".join(str(level) for level in experience_levels)
    if start > 0:
        params["start"] = str(start)
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


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
