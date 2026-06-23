from __future__ import annotations

from typing import TYPE_CHECKING

from .base import JobSource
from .csv_source import CSVSource
from .indeed_browser import IndeedBrowserSource
from .linkedin_browser import LinkedInBrowserSource
from .remotive import RemotiveSource
from .rss import RSSSource

if TYPE_CHECKING:
    from ..config import SourceConfig


def build_source(config: "SourceConfig") -> JobSource:
    if config.type == "csv":
        return CSVSource(name=config.name, path=str(config.options["path"]))
    if config.type == "remotive":
        return RemotiveSource(
            name=config.name,
            search=config.options.get("search"),
            category=config.options.get("category"),
        )
    if config.type == "rss":
        return RSSSource(
            name=config.name,
            url=str(config.options["url"]),
            default_company=str(config.options.get("default_company", "Unknown")),
        )
    if config.type == "linkedin_browser":
        searches = config.options.get("searches")
        if searches is not None:
            searches = [str(search) for search in searches]
        return LinkedInBrowserSource(
            name=config.name,
            profile_dir=config.options.get("profile_dir"),
            searches=searches,
            location=config.options.get("location"),
            experience_levels=[
                str(level)
                for level in config.options.get("experience_levels", [])
            ],
            locale=str(config.options.get("locale", "en-US")),
            max_results_per_search=int(config.options.get("max_results_per_search", 0)),
            max_pages_per_search=int(config.options.get("max_pages_per_search", 0)),
            feed_scrolls=int(config.options.get("feed_scrolls", 4)),
            result_scrolls=int(config.options.get("result_scrolls", 40)),
            easy_apply_only=bool(config.options.get("easy_apply_only", False)),
            exclude_title_keywords=[
                str(keyword)
                for keyword in config.options.get("exclude_title_keywords", [])
            ],
        )
    if config.type == "indeed_browser":
        searches = config.options.get("searches")
        if searches is not None:
            searches = [str(search) for search in searches]
        return IndeedBrowserSource(
            name=config.name,
            profile_dir=config.options.get("profile_dir"),
            base_url=str(config.options.get("base_url", "https://ch.indeed.com/jobs")),
            searches=searches,
            location=config.options.get("location"),
            locale=str(config.options.get("locale", "en-US")),
            max_results_per_search=int(config.options.get("max_results_per_search", 0)),
            max_pages_per_search=int(config.options.get("max_pages_per_search", 0)),
            result_scrolls=int(config.options.get("result_scrolls", 40)),
            exclude_title_keywords=[
                str(keyword)
                for keyword in config.options.get("exclude_title_keywords", [])
            ],
        )
    raise ValueError(f"Unsupported source type: {config.type}")
