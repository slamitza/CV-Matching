from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from collections import defaultdict
import multiprocessing

from .config import Settings, SourceConfig
from .database import Database
from .matcher import build_profile, score_job
from .models import JobPosting
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
    enabled_sources = _select_sources(settings, source_names)
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


def scan_parallel(
    settings: Settings,
    *,
    source_names: set[str],
    dry_run: bool = False,
    max_workers: int = 2,
) -> list[ScanSummary]:
    database = Database(settings.database_path)
    database.init()

    profile = None
    if settings.score_jobs:
        cv_text = settings.cv_path.read_text(encoding="utf-8")
        profile = build_profile(cv_text, settings.required_keywords)

    selected_sources = _select_sources(settings, source_names)
    if not selected_sources:
        raise ValueError("No enabled sources matched the requested scan.")

    scan_ids = {
        source.name: None if dry_run else database.start_scan(source.name)
        for source in selected_sources
    }
    mp_context = multiprocessing.get_context("spawn")
    results_by_source: dict[str, ScanSummary] = {}

    for batch in _source_batches_by_site(selected_sources):
        workers = max(1, min(max_workers, len(batch)))
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp_context) as executor:
            future_to_source = {
                executor.submit(_fetch_source_postings, source_config): source_config
                for source_config in batch
            }
            for future in as_completed(future_to_source):
                source_config = future_to_source[future]
                found_count = 0
                new_count = 0
                updated_count = 0
                error = None
                postings: list[JobPosting] = []

                try:
                    postings, error = future.result()
                    found_count = len(postings)
                    if error is None:
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

                scan_id = scan_ids[source_config.name]
                if scan_id is not None:
                    database.finish_scan(
                        scan_id,
                        found_count=found_count,
                        new_count=new_count,
                        updated_count=updated_count,
                        error=error,
                    )
                results_by_source[source_config.name] = ScanSummary(
                    source=source_config.name,
                    found_count=found_count,
                    new_count=new_count,
                    updated_count=updated_count,
                    error=error,
                )

    return [results_by_source[source.name] for source in selected_sources]


def _select_sources(settings: Settings, source_names: set[str] | None) -> list[SourceConfig]:
    if source_names is None:
        return [source for source in settings.sources if source.enabled]
    return [source for source in settings.sources if source.name in source_names]


def _fetch_source_postings(source_config: SourceConfig) -> tuple[list[JobPosting], str | None]:
    try:
        source = build_source(source_config)
        return list(source.fetch()), None
    except Exception as exc:  # noqa: BLE001 - send source failure back to parent.
        return [], str(exc)


def _source_batches_by_site(source_configs: list[SourceConfig]) -> list[list[SourceConfig]]:
    pending_by_site: dict[str, list[SourceConfig]] = defaultdict(list)
    site_order: list[str] = []
    for source_config in source_configs:
        site_key = _site_key(source_config)
        if site_key not in pending_by_site:
            site_order.append(site_key)
        pending_by_site[site_key].append(source_config)

    batches: list[list[SourceConfig]] = []
    while any(pending_by_site.values()):
        batch = []
        for site_key in site_order:
            if pending_by_site[site_key]:
                batch.append(pending_by_site[site_key].pop(0))
        batches.append(batch)
    return batches


def _site_key(source_config: SourceConfig) -> str:
    if source_config.type == "linkedin_browser":
        return "linkedin"
    if source_config.type == "indeed_browser":
        return "indeed"
    return source_config.name
