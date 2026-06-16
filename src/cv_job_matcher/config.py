from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11 after install.
    import tomli as tomllib


@dataclass(frozen=True)
class SourceConfig:
    name: str
    type: str
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    cv_path: Path
    minimum_score: float
    search_terms: list[str]
    required_keywords: list[str]
    sources: list[SourceConfig]


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path)
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    cv_config = data.get("cv", {})
    source_configs = []
    for source in data.get("sources", []):
        options = {
            key: value
            for key, value in source.items()
            if key not in {"name", "type", "enabled"}
        }
        source_configs.append(
            SourceConfig(
                name=str(source["name"]),
                type=str(source["type"]),
                enabled=bool(source.get("enabled", True)),
                options=options,
            )
        )

    return Settings(
        database_path=Path(data.get("database_path", "data/job_matcher.sqlite3")),
        cv_path=Path(cv_config.get("path", "data/cv.txt")),
        minimum_score=float(data.get("minimum_score", 0)),
        search_terms=[str(term) for term in data.get("search_terms", [])],
        required_keywords=[str(term).lower() for term in cv_config.get("required_keywords", [])],
        sources=source_configs,
    )
