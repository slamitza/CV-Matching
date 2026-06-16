from __future__ import annotations

from ..config import SourceConfig
from .base import JobSource
from .csv_source import CSVSource
from .remotive import RemotiveSource
from .rss import RSSSource


def build_source(config: SourceConfig) -> JobSource:
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
    raise ValueError(f"Unsupported source type: {config.type}")
