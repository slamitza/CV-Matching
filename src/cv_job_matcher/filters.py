from __future__ import annotations

from .models import JobPosting


def company_is_excluded(company: str | None, excluded_companies: list[str]) -> bool:
    normalized_company = _normalize_company(company)
    if not normalized_company:
        return False
    return any(
        excluded_company in normalized_company
        for excluded_company in _normalized_company_filters(excluded_companies)
    )


def filter_excluded_companies(
    postings: list[JobPosting],
    excluded_companies: list[str],
) -> list[JobPosting]:
    if not excluded_companies:
        return postings
    return [
        posting
        for posting in postings
        if not company_is_excluded(posting.company, excluded_companies)
    ]


def _normalized_company_filters(excluded_companies: list[str]) -> list[str]:
    return [
        normalized
        for company in excluded_companies
        if (normalized := _normalize_company(company))
    ]


def _normalize_company(company: str | None) -> str:
    return " ".join(str(company or "").casefold().split())
