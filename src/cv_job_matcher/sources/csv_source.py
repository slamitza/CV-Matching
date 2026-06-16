from __future__ import annotations

from pathlib import Path
import csv

from ..models import JobPosting
from .base import JobSource


class CSVSource(JobSource):
    def __init__(self, name: str, path: str):
        super().__init__(name)
        self.path = Path(path)

    def fetch(self) -> list[JobPosting]:
        if not self.path.exists():
            return []

        postings: list[JobPosting] = []
        with self.path.open(newline="", encoding="utf-8") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                source_id = row.get("source_id") or row.get("url") or f"{self.path}:{index}"
                postings.append(
                    JobPosting(
                        source=self.name,
                        source_id=source_id,
                        title=row.get("title") or "Untitled",
                        company=row.get("company") or "Unknown",
                        location=row.get("location") or None,
                        url=row.get("url") or None,
                        description=row.get("description") or "",
                        posted_at=row.get("posted_at") or None,
                        remote=_parse_bool(row.get("remote")),
                        raw=dict(row),
                    )
                )
        return postings


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "remote"}:
        return True
    if normalized in {"0", "false", "no", "n", "onsite"}:
        return False
    return None
