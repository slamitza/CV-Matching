from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
import hashlib
import random
import re

from ..browser_runtime import configure_browser_context, goto_domcontentloaded, load_browser_runtime
from ..models import JobPosting
from .base import JobSource


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE_DIR = ROOT_DIR / "data" / "browser-profiles" / "indeed-job-search"
DEFAULT_BASE_URL = "https://ch.indeed.com/jobs"
DEFAULT_SEARCHES = [
    "Data Science",
    "Bioinformatics",
    "AI engineer",
    "ML engineer",
    "Data Scientist",
    "Biostatistic",
    "Biostatistician",
    "Research Engineer",
]

SECURITY_PROMPTS = [
    "captcha",
    "verify you are human",
    "unusual traffic",
    "additional verification",
    "security check",
]
ABSOLUTE_PAGE_SAFETY_LIMIT = 50
INDEED_RESULTS_PER_PAGE = 10


class IndeedBrowserSource(JobSource):
    def __init__(
        self,
        name: str,
        *,
        profile_dir: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        searches: list[str] | None = None,
        location: str | None = None,
        locale: str = "en-US",
        max_results_per_search: int = 0,
        max_pages_per_search: int = 0,
        result_scrolls: int = 40,
        exclude_title_keywords: list[str] | None = None,
    ):
        super().__init__(name)
        self.profile_dir = _resolve_profile_dir(profile_dir)
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.searches = searches or DEFAULT_SEARCHES
        self.location = location
        self.locale = locale
        self.max_results_per_search = max_results_per_search
        self.max_pages_per_search = max_pages_per_search
        self.result_scrolls = result_scrolls
        self.exclude_title_keywords = [
            keyword.lower() for keyword in (exclude_title_keywords or [])
        ]

    def fetch(self) -> list[JobPosting]:
        BrowserError, sync_playwright = load_browser_runtime()

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        postings: dict[str, JobPosting] = {}

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                locale=self.locale,
                args=[f"--lang={self.locale}"],
                viewport={"width": 1440, "height": 1000},
            )
            configure_browser_context(context)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                goto_domcontentloaded(page, self.base_url)
                self._wait(page, 2, 3, noise_mean=1, noise_std=1)
                self._accept_cookie_prompt(page)
                self._stop_on_security_prompt(page)

                for search in self.searches:
                    goto_domcontentloaded(page, self._search_url(search))
                    self._wait(page, 2, 3, noise_mean=1, noise_std=1)
                    self._accept_cookie_prompt(page)
                    self._stop_on_security_prompt(page)

                    for posting in self._collect_search_pages(page, search):
                        postings[posting.source_id] = posting
                    self._wait(page, 2, 3, noise_mean=1, noise_std=1)
            except BrowserError as exc:
                raise RuntimeError(f"Indeed browser scan failed: {exc}") from exc
            finally:
                context.close()

        return list(postings.values())

    def _collect_search_pages(self, page: object, search: str) -> list[JobPosting]:
        postings: dict[str, JobPosting] = {}
        page_limit = (
            self.max_pages_per_search
            if self.max_pages_per_search > 0
            else ABSOLUTE_PAGE_SAFETY_LIMIT
        )

        for page_index in range(page_limit):
            before_count = len(postings)
            page_postings = self._collect_search_results(page, search)
            for posting in page_postings:
                postings[posting.source_id] = posting

            if not page_postings:
                break

            if self.max_results_per_search > 0 and len(postings) >= self.max_results_per_search:
                break

            if len(postings) == before_count and page_index > 0:
                break

            if not self._go_to_next_results_page(page, search, page_index + 1):
                break

            self._wait(page, 2, 3, noise_mean=1, noise_std=1)
            self._accept_cookie_prompt(page)
            self._stop_on_security_prompt(page)

        return list(postings.values())

    def _collect_search_results(self, page: object, search: str) -> list[JobPosting]:
        postings: dict[str, JobPosting] = {}
        rounds_without_new_jobs = 0

        for _index in range(self.result_scrolls + 1):
            before_count = len(postings)
            for posting in self._collect_visible_listings(page, search):
                postings[posting.source_id] = posting

            if self.max_results_per_search > 0 and len(postings) >= self.max_results_per_search:
                break

            if len(postings) == before_count:
                rounds_without_new_jobs += 1
            else:
                rounds_without_new_jobs = 0

            if rounds_without_new_jobs >= 3:
                break

            page.mouse.wheel(0, random.randint(450, 900))
            self._wait(page, 2, 3, noise_mean=1, noise_std=1)
            self._stop_on_security_prompt(page)

        return list(postings.values())

    def _collect_visible_listings(self, page: object, search: str) -> list[JobPosting]:
        cards = _job_card_locators(page)
        postings: list[JobPosting] = []
        card_count = cards.count()

        if self.max_results_per_search > 0:
            card_count = min(card_count, self.max_results_per_search)

        for index in range(card_count):
            card = cards.nth(index)
            try:
                if not card.is_visible():
                    continue
            except Exception:
                continue

            data_jk = _safe_get_attribute(card, "data-jk")
            raw_url = _first_attr(
                card,
                [
                    'a[href*="/viewjob"]',
                    'a[href*="jk="]',
                    "h2.jobTitle a",
                    'a[data-jk]',
                ],
                "href",
            )
            card_text = _clean_text(_safe_inner_text(card))
            title = _first_text(
                card,
                [
                    '[data-testid="job-title"]',
                    "h2.jobTitle",
                    "h2.jobTitle a",
                    'a[data-jk]',
                    'a[href*="/viewjob"]',
                ],
            )
            company = _first_text(
                card,
                [
                    '[data-testid="company-name"]',
                    ".companyName",
                    '[data-testid="companyName"]',
                ],
            )
            location = _first_text(
                card,
                [
                    '[data-testid="text-location"]',
                    '[data-testid="job-location"]',
                    ".companyLocation",
                ],
            )

            fallback_lines = [line for line in _safe_inner_text(card).splitlines() if line.strip()]
            title = _clean_text(title or (fallback_lines[0] if fallback_lines else "Untitled"))
            company = _clean_text(company or (fallback_lines[1] if len(fallback_lines) > 1 else "Unknown"))
            location = _clean_text(location or (fallback_lines[2] if len(fallback_lines) > 2 else ""))
            if _title_has_excluded_keyword(title, self.exclude_title_keywords):
                continue
            source_id = _indeed_job_id(data_jk, raw_url, title, company)
            url = _normalize_indeed_url(raw_url, self.base_url, source_id)
            if not url:
                continue

            postings.append(
                JobPosting(
                    source=self.name,
                    source_id=source_id,
                    title=title,
                    company=company,
                    location=location or None,
                    url=url,
                    description=card_text,
                    posted_at="last-24h",
                    raw={
                        "search": search,
                        "source": "indeed_browser",
                        "profile_dir": str(self.profile_dir),
                    },
                )
            )

        return postings

    def _go_to_next_results_page(self, page: object, search: str, next_page_index: int) -> bool:
        if self._click_next_results_page(page):
            return True

        next_start = next_page_index * INDEED_RESULTS_PER_PAGE
        current_start = _current_start_param(page.url)
        if current_start is not None and current_start >= next_start:
            return False

        goto_domcontentloaded(page, self._search_url(search, start=next_start))
        return True

    def _click_next_results_page(self, page: object) -> bool:
        next_buttons = [
            page.get_by_role("link", name=re.compile(r"Next", re.I)),
            page.get_by_role("button", name=re.compile(r"Next", re.I)),
            page.locator('a[aria-label*="Next"]').first,
            page.locator('a[data-testid="pagination-page-next"]').first,
            page.locator('a[rel="next"]').first,
        ]
        for button in next_buttons:
            try:
                if button.count() > 0 and button.first.is_enabled(timeout=1000):
                    button.first.click(timeout=3000)
                    return True
            except Exception:
                continue
        return False

    def _search_url(self, query: str, *, start: int | None = None) -> str:
        params = {
            "q": query,
            "fromage": "1",
            "sort": "date",
        }
        if self.location:
            params["l"] = self.location
        if start is not None:
            params["start"] = str(start)
        return f"{self.base_url}?{urlencode(params)}"

    def _accept_cookie_prompt(self, page: object) -> None:
        buttons = [
            page.get_by_role("button", name=re.compile(r"Accept all|Accept|I agree", re.I)),
            page.locator('button:has-text("Accept")').first,
        ]
        for button in buttons:
            try:
                if button.count() > 0 and button.first.is_visible(timeout=1000):
                    button.first.click(timeout=2000)
                    self._wait(page, 1, 2, noise_mean=0.5, noise_std=0.5)
                    return
            except Exception:
                continue

    def _wait(
        self,
        page: object,
        min_seconds: float,
        max_seconds: float,
        *,
        noise_mean: float,
        noise_std: float,
    ) -> None:
        seconds = random.uniform(min_seconds, max_seconds) + random.gauss(noise_mean, noise_std)
        seconds = max(0.75, min(seconds, 12.0))
        page.wait_for_timeout(int(seconds * 1000))

    def _stop_on_security_prompt(self, page: object) -> None:
        text = _safe_page_text(page).lower()
        if any(prompt in text for prompt in SECURITY_PROMPTS):
            raise RuntimeError(
                "Indeed showed a CAPTCHA or security prompt. "
                "Stopping so you can handle it manually."
            )


def _resolve_profile_dir(profile_dir: str | None) -> Path:
    path = Path(profile_dir or DEFAULT_PROFILE_DIR).expanduser()
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _job_card_locators(page: object) -> object:
    selectors = [
        "[data-jk]",
        ".job_seen_beacon",
        "td.resultContent",
        "div.cardOutline",
    ]
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            return locator
    return page.locator("__missing_indeed_job_card__")


def _first_text(parent: object, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            locator = parent.locator(selector).first
            if locator.count() > 0:
                text = _clean_text(locator.inner_text(timeout=1000))
                if text:
                    return text
        except Exception:
            continue
    return None


def _first_attr(parent: object, selectors: list[str], attr: str) -> str | None:
    for selector in selectors:
        try:
            locator = parent.locator(selector).first
            if locator.count() > 0:
                value = locator.get_attribute(attr, timeout=1000)
                if value:
                    return value
        except Exception:
            continue
    return None


def _safe_get_attribute(locator: object, attr: str) -> str | None:
    try:
        return locator.get_attribute(attr, timeout=1000)
    except Exception:
        return None


def _normalize_indeed_url(url: str | None, base_url: str = DEFAULT_BASE_URL, job_id: str | None = None) -> str | None:
    origin = _base_origin(base_url)
    if job_id and not job_id.startswith("indeed-"):
        return f"{origin}/viewjob?jk={job_id}"
    if not url:
        return None
    absolute_url = urljoin(origin, url)
    parsed = urlparse(absolute_url)
    jk = _job_key_from_url(absolute_url)
    if jk:
        return f"{origin}/viewjob?jk={jk}"
    return parsed._replace(fragment="").geturl()


def _indeed_job_id(data_jk: str | None, url: str | None, title: str, company: str) -> str:
    if data_jk:
        return data_jk
    job_key = _job_key_from_url(url)
    if job_key:
        return job_key
    digest = hashlib.sha1(f"{url}|{title}|{company}".encode("utf-8")).hexdigest()
    return f"indeed-{digest[:16]}"


def _job_key_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        values = parse_qs(urlparse(url).query).get("jk")
        if values:
            return values[0]
    except ValueError:
        return None
    return None


def _base_origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "https://ch.indeed.com"


def _safe_inner_text(locator: object) -> str:
    try:
        return locator.inner_text(timeout=1000)
    except Exception:
        return ""


def _safe_page_text(page: object) -> str:
    try:
        return page.locator("body").inner_text(timeout=1000)
    except Exception:
        return ""


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _title_has_excluded_keyword(title: str, excluded_keywords: list[str]) -> bool:
    normalized_title = title.lower()
    return any(keyword in normalized_title for keyword in excluded_keywords)


def _current_start_param(url: str) -> int | None:
    try:
        values = parse_qs(urlparse(url).query).get("start")
        if not values:
            return None
        return int(values[0])
    except ValueError:
        return None
