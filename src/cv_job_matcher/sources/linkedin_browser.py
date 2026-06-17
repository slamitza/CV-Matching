from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
import hashlib
import random
import re

from ..models import JobPosting
from .base import JobSource


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE_DIR = ROOT_DIR / "data" / "browser-profiles" / "linkedin-job-search"
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

JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")
SECURITY_PROMPTS = [
    "security verification",
    "captcha",
    "unusual activity",
    "verify your identity",
    "two-step verification",
    "checkpoint",
]
ABSOLUTE_PAGE_SAFETY_LIMIT = 50


class LinkedInBrowserSource(JobSource):
    def __init__(
        self,
        name: str,
        *,
        profile_dir: str | None = None,
        searches: list[str] | None = None,
        location: str | None = None,
        locale: str = "en-US",
        max_results_per_search: int = 0,
        max_pages_per_search: int = 0,
        feed_scrolls: int = 4,
        result_scrolls: int = 40,
        exclude_title_keywords: list[str] | None = None,
    ):
        super().__init__(name)
        self.profile_dir = _resolve_profile_dir(profile_dir)
        self.searches = searches or DEFAULT_SEARCHES
        self.location = location
        self.locale = locale
        self.max_results_per_search = max_results_per_search
        self.max_pages_per_search = max_pages_per_search
        self.feed_scrolls = feed_scrolls
        self.result_scrolls = result_scrolls
        self.exclude_title_keywords = [
            keyword.lower() for keyword in (exclude_title_keywords or [])
        ]

    def fetch(self) -> list[JobPosting]:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run: python -m pip install -e . "
                "and python -m playwright install chromium"
            ) from exc

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
            try:
                page = context.pages[0] if context.pages else context.new_page()
                self._warm_up_feed(page)

                for search in self.searches:
                    self._run_search(page, search)
                    for posting in self._collect_search_pages(page, search):
                        postings[posting.source_id] = posting
                    self._wait(page, 2, 3, noise_mean=1, noise_std=1)
            except PlaywrightError as exc:
                raise RuntimeError(f"LinkedIn browser scan failed: {exc}") from exc
            finally:
                context.close()

        return list(postings.values())

    def _warm_up_feed(self, page: object) -> None:
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        self._wait(page, 2, 3, noise_mean=1, noise_std=1.5)
        self._stop_on_security_prompt(page)
        self._stop_if_logged_out(page)

        for _index in range(self.feed_scrolls):
            page.mouse.wheel(0, random.randint(350, 850))
            self._wait(page, 2, 3, noise_mean=1, noise_std=1.5)
            self._stop_on_security_prompt(page)

    def _run_search(self, page: object, query: str) -> None:
        page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
        self._wait(page, 2, 3, noise_mean=1, noise_std=1.5)
        self._stop_if_logged_out(page)

        if not self._type_jobs_search(page, query):
            page.goto(self._search_url(query), wait_until="domcontentloaded")

        self._wait(page, 2, 3, noise_mean=1, noise_std=1.5)
        self._apply_recent_filter(page, query)
        self._wait(page, 2, 3, noise_mean=1, noise_std=1)
        self._stop_on_security_prompt(page)

    def _type_jobs_search(self, page: object, query: str) -> bool:
        keyword_selectors = [
            'input[aria-label*="Search by title"]',
            'input[aria-label*="Search jobs"]',
            'input[id^="jobs-search-box-keyword"]',
        ]
        location_selectors = [
            'input[aria-label*="City, state"]',
            'input[aria-label*="Location"]',
            'input[id^="jobs-search-box-location"]',
        ]

        keyword_input = _first_visible_locator(page, keyword_selectors)
        if keyword_input is None:
            return False

        keyword_input.fill("")
        keyword_input.type(query, delay=random.randint(50, 140))

        if self.location:
            location_input = _first_visible_locator(page, location_selectors)
            if location_input is not None:
                location_input.fill("")
                location_input.type(self.location, delay=random.randint(50, 140))

        page.keyboard.press("Enter")
        return True

    def _apply_recent_filter(self, page: object, query: str) -> None:
        try:
            page.get_by_role("button", name=re.compile("Date posted", re.I)).click(timeout=5000)
            self._wait(page, 2, 3, noise_mean=1, noise_std=1)
            page.get_by_text(re.compile("Past 24 hours", re.I)).click(timeout=5000)
            self._wait(page, 2, 3, noise_mean=1, noise_std=1)
            show_results = page.get_by_role("button", name=re.compile("Show results", re.I))
            if show_results.count() > 0:
                show_results.first.click(timeout=5000)
        except Exception:
            page.goto(self._search_url(query), wait_until="domcontentloaded")

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

    def _collect_search_pages(self, page: object, search: str) -> list[JobPosting]:
        postings: dict[str, JobPosting] = {}

        page_limit = (
            self.max_pages_per_search
            if self.max_pages_per_search > 0
            else ABSOLUTE_PAGE_SAFETY_LIMIT
        )
        for page_index in range(page_limit):
            for posting in self._collect_search_results(page, search):
                postings[posting.source_id] = posting

            if self.max_results_per_search > 0 and len(postings) >= self.max_results_per_search:
                break

            if _visible_job_card_count(page) == 0:
                break

            if not self._go_to_next_results_page(page, search, page_index + 1):
                break

            self._wait(page, 2, 3, noise_mean=1, noise_std=1)
            self._stop_on_security_prompt(page)

        return list(postings.values())

    def _go_to_next_results_page(self, page: object, search: str, next_page_index: int) -> bool:
        if self._click_next_results_page(page):
            return True

        next_start = next_page_index * 25
        current_start = _current_start_param(page.url)
        if current_start is not None and current_start >= next_start:
            return False

        page.goto(self._search_url(search, start=next_start), wait_until="domcontentloaded")
        return True

    def _click_next_results_page(self, page: object) -> bool:
        next_buttons = [
            page.get_by_role("button", name=re.compile(r"Next", re.I)),
            page.locator('button[aria-label*="Next"]').first,
        ]
        for button in next_buttons:
            try:
                if button.count() > 0 and button.first.is_enabled(timeout=1000):
                    button.first.click(timeout=3000)
                    return True
            except Exception:
                continue
        return False

    def _collect_visible_listings(self, page: object, search: str) -> list[JobPosting]:
        cards = _job_card_locators(page)
        postings: list[JobPosting] = []

        card_count = cards.count()
        if self.max_results_per_search > 0:
            card_count = min(card_count, self.max_results_per_search)

        for index in range(card_count):
            card = cards.nth(index)
            if not card.is_visible():
                continue

            raw_url = _first_attr(card, ['a[href*="/jobs/view/"]'], "href")
            url = _normalize_linkedin_url(raw_url)
            card_text = _clean_text(_safe_inner_text(card))
            title = _first_text(
                card,
                [
                    ".job-card-list__title--link",
                    ".job-card-list__title",
                    ".job-card-container__link",
                    'a[href*="/jobs/view/"]',
                ],
            )
            company = _first_text(
                card,
                [
                    ".artdeco-entity-lockup__subtitle",
                    ".job-card-container__primary-description",
                ],
            )
            location = _first_text(
                card,
                [
                    ".artdeco-entity-lockup__caption",
                    ".job-card-container__metadata-item",
                ],
            )

            fallback_lines = [line for line in _safe_inner_text(card).splitlines() if line.strip()]
            title = _clean_text(title or (fallback_lines[0] if fallback_lines else "Untitled"))
            company = _clean_text(company or (fallback_lines[1] if len(fallback_lines) > 1 else "Unknown"))
            location = _clean_text(location or (fallback_lines[2] if len(fallback_lines) > 2 else ""))
            if _title_has_excluded_keyword(title, self.exclude_title_keywords):
                continue
            source_id = _source_id(card.get_attribute("data-job-id"), url, title, company)

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
                        "source": "linkedin_browser",
                        "profile_dir": str(self.profile_dir),
                    },
                )
            )

        return postings

    def _search_url(self, query: str, *, start: int | None = None) -> str:
        params = {
            "keywords": query,
            "f_TPR": "r86400",
        }
        if self.location:
            params["location"] = self.location
        if start is not None:
            params["start"] = str(start)
        return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"

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

    def _stop_if_logged_out(self, page: object) -> None:
        if "/login" in page.url or page.locator('input[name="session_key"]').count() > 0:
            raise RuntimeError(
                "LinkedIn profile is not logged in. Run scripts/open_linkedin_profile.sh "
                "and log in manually before scanning."
            )

    def _stop_on_security_prompt(self, page: object) -> None:
        text = _safe_page_text(page).lower()
        if any(prompt in text for prompt in SECURITY_PROMPTS):
            raise RuntimeError(
                "LinkedIn showed a security, MFA, or CAPTCHA-style prompt. "
                "Stopping so you can handle it manually."
            )


def _resolve_profile_dir(profile_dir: str | None) -> Path:
    path = Path(profile_dir or DEFAULT_PROFILE_DIR).expanduser()
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _first_visible_locator(page: object, selectors: list[str]) -> object | None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() > 0 and locator.is_visible(timeout=1000):
                return locator
        except Exception:
            continue
    return None


def _job_card_locators(page: object) -> object:
    selectors = [
        ".job-card-container",
        "li.jobs-search-results__list-item",
        "[data-job-id]",
    ]
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            return locator
    return page.locator("__missing_linkedin_job_card__")


def _visible_job_card_count(page: object) -> int:
    cards = _job_card_locators(page)
    try:
        card_count = cards.count()
    except Exception:
        return 0
    visible_count = 0
    for index in range(card_count):
        try:
            if cards.nth(index).is_visible(timeout=500):
                visible_count += 1
        except Exception:
            continue
    return visible_count


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


def _normalize_linkedin_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("/"):
        url = f"https://www.linkedin.com{url}"
    return url.split("?")[0].rstrip("/")


def _source_id(data_job_id: str | None, url: str | None, title: str, company: str) -> str:
    if data_job_id:
        return data_job_id
    if url:
        match = JOB_ID_RE.search(url)
        if match:
            return match.group(1)
    digest = hashlib.sha1(f"{url}|{title}|{company}".encode("utf-8")).hexdigest()
    return f"linkedin-{digest[:16]}"


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
