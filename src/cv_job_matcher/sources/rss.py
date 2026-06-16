from __future__ import annotations

from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from ..models import JobPosting
from .base import JobSource


class RSSSource(JobSource):
    def __init__(self, name: str, url: str, default_company: str = "Unknown"):
        super().__init__(name)
        self.url = url
        self.default_company = default_company

    def fetch(self) -> list[JobPosting]:
        request = Request(self.url, headers={"User-Agent": "cv-job-matcher/0.1"})
        with urlopen(request, timeout=30) as response:
            root = ET.fromstring(response.read())

        postings = []
        for index, item in enumerate(_iter_feed_items(root), start=1):
            title = _first_text(item, ["title"]) or "Untitled"
            link = _first_text(item, ["link"])
            if link is None:
                link = _link_href(item)
            source_id = _first_text(item, ["guid", "id"]) or link or f"{self.url}#{index}"
            description = _first_text(item, ["description", "summary", "content"]) or ""
            posted_at = _first_text(item, ["pubDate", "published", "updated"])
            company = _first_text(item, ["company", "author"]) or self.default_company
            postings.append(
                JobPosting(
                    source=self.name,
                    source_id=source_id,
                    title=title,
                    company=company,
                    url=link,
                    description=description,
                    posted_at=posted_at,
                    raw={"feed_url": self.url},
                )
            )
        return postings


def _iter_feed_items(root: ET.Element) -> list[ET.Element]:
    items = list(root.findall(".//item"))
    if items:
        return items
    return list(root.findall(".//{*}entry"))


def _first_text(element: ET.Element, names: list[str]) -> str | None:
    for name in names:
        child = element.find(name)
        if child is None:
            child = element.find(f"{{*}}{name}")
        if child is not None and child.text:
            return child.text.strip()
    return None


def _link_href(element: ET.Element) -> str | None:
    for child in element.findall("{*}link"):
        href = child.attrib.get("href")
        if href:
            return href
    return None
