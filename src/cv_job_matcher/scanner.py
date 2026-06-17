from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .database import Database
from .matcher import build_profile, score_job
from .models import MatchResult
from .sources import build_source


@dataclass(frozen=True)
class ScanSummary:
    source: str
    found_count: int
    new_count: int
    updated_count: int
    error: str | None = None


def scan(settings: Settings, *, source_names: set[str] | None = None, dry_run: bool = False) -> list[ScanSummary]:
    database = Database(settings.database_path)
    database.init()

    profile = None
    if settings.score_jobs:
        cv_text = settings.cv_path.read_text(encoding="utf-8")
        profile = build_profile(cv_text, settings.required_keywords)

    summaries: list[ScanSummary] = []
    if source_names is None:
        enabled_sources = [source for source in settings.sources if source.enabled]
    else:
        enabled_sources = [source for source in settings.sources if source.name in source_names]
    if not enabled_sources:
        raise ValueError("No enabled sources matched the requested scan.")

    for source_config in enabled_sources:
        scan_id = None if dry_run else database.start_scan(source_config.name)
        found_count = 0
        new_count = 0
        updated_count = 0
        error = None

        try:
            source = build_source(source_config)
            postings = list(source.fetch())
            found_count = len(postings)
            for posting in postings:
                result = (
                    score_job(profile, posting)
                    if profile is not None
                    else MatchResult(score=0.0, matched_keywords=[], missing_keywords=[])
                )
                if dry_run:
                    continue
                inserted = database.upsert_job(posting, result)
                if inserted:
                    new_count += 1
                else:
                    updated_count += 1
        except Exception as exc:  # noqa: BLE001 - record source failure and continue.
            error = str(exc)

        if scan_id is not None:
            database.finish_scan(
                scan_id,
                found_count=found_count,
                new_count=new_count,
                updated_count=updated_count,
                error=error,
            )
        summaries.append(
            ScanSummary(
                source=source_config.name,
                found_count=found_count,
                new_count=new_count,
                updated_count=updated_count,
                error=error,
            )
        )

    return summaries
