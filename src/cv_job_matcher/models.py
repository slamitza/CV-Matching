from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobPosting:
    source: str
    source_id: str
    title: str
    company: str
    location: str | None = None
    url: str | None = None
    description: str = ""
    posted_at: str | None = None
    remote: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchResult:
    score: float
    matched_keywords: list[str]
    missing_keywords: list[str]
