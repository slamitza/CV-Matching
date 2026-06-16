from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from ..models import JobPosting
from .base import JobSource


class RemotiveSource(JobSource):
    API_URL = "https://remotive.com/api/remote-jobs"

    def __init__(self, name: str, search: str | None = None, category: str | None = None):
        super().__init__(name)
        self.search = search
        self.category = category

    def fetch(self) -> Iterable[JobPosting]:
        params = {}
        if self.search:
            params["search"] = self.search
        if self.category:
            params["category"] = self.category

        url = self.API_URL
        if params:
            url = f"{url}?{urlencode(params)}"

        request = Request(url, headers={"User-Agent": "cv-job-matcher/0.1"})
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        postings = []
        for item in payload.get("jobs", []):
            job_id = str(item.get("id") or item.get("url"))
            postings.append(
                JobPosting(
                    source=self.name,
                    source_id=job_id,
                    title=str(item.get("title") or "Untitled"),
                    company=str(item.get("company_name") or "Unknown"),
                    location=item.get("candidate_required_location") or "Remote",
                    url=item.get("url"),
                    description=item.get("description") or "",
                    posted_at=item.get("publication_date"),
                    remote=True,
                    raw=item,
                )
            )
        return postings
