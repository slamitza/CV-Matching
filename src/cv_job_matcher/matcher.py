from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from .models import JobPosting, MatchResult


STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "but",
    "can",
    "for",
    "from",
    "has",
    "have",
    "into",
    "our",
    "the",
    "their",
    "this",
    "to",
    "with",
    "you",
    "your",
    "will",
    "work",
    "team",
    "role",
    "job",
    "skills",
    "experience",
}


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}")
SHORT_TECH_TERMS = {"ai", "ml"}


@dataclass(frozen=True)
class CVProfile:
    keywords: list[str]
    required_keywords: list[str]


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw_token in TOKEN_RE.findall(text):
        token = raw_token.lower().strip(".-")
        if token not in STOP_WORDS and (len(token) > 2 or token in SHORT_TECH_TERMS):
            tokens.append(token)
    return tokens


def extract_keywords(text: str, limit: int = 60) -> list[str]:
    counts = Counter(tokenize(text))
    return [keyword for keyword, _count in counts.most_common(limit)]


def build_profile(cv_text: str, required_keywords: list[str] | None = None) -> CVProfile:
    required = [keyword.lower() for keyword in (required_keywords or [])]
    keywords = extract_keywords(cv_text)
    for keyword in reversed(required):
        if keyword not in keywords:
            keywords.insert(0, keyword)
    return CVProfile(keywords=keywords, required_keywords=required)


def score_job(profile: CVProfile, job: JobPosting) -> MatchResult:
    weighted_text = " ".join(
        [
            job.title,
            job.title,
            job.company,
            job.location or "",
            job.description,
        ]
    )
    job_tokens = set(tokenize(weighted_text))

    if not profile.keywords:
        return MatchResult(score=0.0, matched_keywords=[], missing_keywords=[])

    matched = sorted(keyword for keyword in profile.keywords if keyword in job_tokens)
    missing_required = sorted(
        keyword for keyword in profile.required_keywords if keyword not in job_tokens
    )

    keyword_coverage = len(matched) / max(len(profile.keywords), 1)
    if profile.required_keywords:
        required_matches = [
            keyword for keyword in profile.required_keywords if keyword in job_tokens
        ]
        required_coverage = len(required_matches) / len(profile.required_keywords)
        score = (required_coverage * 0.7) + (keyword_coverage * 0.3)
    else:
        score = keyword_coverage

    if profile.required_keywords:
        missing = missing_required
    else:
        missing = [keyword for keyword in profile.keywords[:10] if keyword not in job_tokens]

    return MatchResult(
        score=round(score * 100, 2),
        matched_keywords=matched[:25],
        missing_keywords=missing[:25],
    )
