from __future__ import annotations

import unittest

from cv_job_matcher.sources.linkedin_browser import (
    ABSOLUTE_PAGE_SAFETY_LIMIT,
    LinkedInBrowserSource,
    _current_start_param,
    _normalize_linkedin_url,
    _source_id,
    _title_has_excluded_keyword,
    _visible_job_card_count,
)


class FakeCard:
    def __init__(self, visible: bool):
        self.visible = visible

    def is_visible(self, timeout: int = 0) -> bool:
        return self.visible


class FakeCards:
    def __init__(self, cards: list[FakeCard]):
        self.cards = cards

    def count(self) -> int:
        return len(self.cards)

    def nth(self, index: int) -> FakeCard:
        return self.cards[index]


class FakePage:
    def __init__(self, cards: list[FakeCard]):
        self.cards = FakeCards(cards)

    def locator(self, selector: str) -> FakeCards:
        return self.cards


class LinkedInBrowserSourceTests(unittest.TestCase):
    def test_normalizes_relative_job_url(self) -> None:
        self.assertEqual(
            "https://www.linkedin.com/jobs/view/123456",
            _normalize_linkedin_url("/jobs/view/123456/?trackingId=abc"),
        )

    def test_source_id_prefers_job_id_from_url(self) -> None:
        self.assertEqual(
            "123456",
            _source_id(None, "https://www.linkedin.com/jobs/view/123456", "Data Scientist", "Acme"),
        )

    def test_source_id_falls_back_to_stable_hash(self) -> None:
        first = _source_id(None, None, "ML Engineer", "Acme")
        second = _source_id(None, None, "ML Engineer", "Acme")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("linkedin-"))

    def test_excluded_title_keyword_is_case_insensitive_substring(self) -> None:
        self.assertTrue(_title_has_excluded_keyword("Senior Medical Writer", ["writer"]))
        self.assertTrue(_title_has_excluded_keyword("Associate Director", ["director"]))
        self.assertTrue(_title_has_excluded_keyword("Biotech Executive", ["executive"]))
        self.assertTrue(_title_has_excluded_keyword("Junior Quantitative Analyst", ["junior"]))
        self.assertFalse(_title_has_excluded_keyword("Senior Medical Researcher", ["writer"]))

    def test_current_start_param(self) -> None:
        self.assertEqual(25, _current_start_param("https://www.linkedin.com/jobs/search/?start=25"))
        self.assertIsNone(_current_start_param("https://www.linkedin.com/jobs/search/"))

    def test_zero_caps_mean_unconfigured_caps(self) -> None:
        source = LinkedInBrowserSource(
            "linkedin-browser",
            max_results_per_search=0,
            max_pages_per_search=0,
        )
        self.assertEqual(0, source.max_results_per_search)
        self.assertEqual(0, source.max_pages_per_search)
        self.assertGreaterEqual(ABSOLUTE_PAGE_SAFETY_LIMIT, 50)

    def test_visible_job_card_count_detects_empty_pages(self) -> None:
        self.assertEqual(0, _visible_job_card_count(FakePage([])))
        self.assertEqual(
            2,
            _visible_job_card_count(
                FakePage([FakeCard(True), FakeCard(False), FakeCard(True)])
            ),
        )


if __name__ == "__main__":
    unittest.main()
