from __future__ import annotations

import unittest

from cv_job_matcher.sources.linkedin_browser import (
    ABSOLUTE_PAGE_SAFETY_LIMIT,
    LinkedInBrowserSource,
    _current_start_param,
    _is_easy_apply_card,
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
        self.assertTrue(_title_has_excluded_keyword("Postdoctoral Researcher", ["doctoral"]))
        self.assertTrue(_title_has_excluded_keyword("Post Doctoral Researcher", ["doctoral"]))
        self.assertTrue(_title_has_excluded_keyword("Data Science Trainee", ["trainee"]))
        self.assertTrue(_title_has_excluded_keyword("Data Science Intern", ["intern"]))
        self.assertTrue(_title_has_excluded_keyword("Machine Learning Internship", ["intern"]))
        self.assertTrue(_title_has_excluded_keyword("Machine Learning Internship", ["internship"]))
        self.assertTrue(_title_has_excluded_keyword("Head of Data Science", ["head of"]))
        self.assertFalse(_title_has_excluded_keyword("Senior Medical Researcher", ["writer"]))
        self.assertFalse(_title_has_excluded_keyword("International Data Scientist", ["intern"]))

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

    def test_search_url_includes_configured_experience_levels(self) -> None:
        source = LinkedInBrowserSource(
            "linkedin-browser",
            location="Zurich",
            experience_levels=["3", "4"],
        )

        url = source._search_url("Data Science")

        self.assertIn("location=Zurich", url)
        self.assertIn("f_E=3%2C4", url)

    def test_search_url_includes_easy_apply_filter_when_configured(self) -> None:
        source = LinkedInBrowserSource(
            "linkedin-browser",
            location="Zurich",
            easy_apply_only=True,
        )

        url = source._search_url("Data Science")

        self.assertIn("f_AL=true", url)

    def test_easy_apply_card_detection(self) -> None:
        self.assertTrue(_is_easy_apply_card("Promoted Easy Apply 1 day ago"))
        self.assertFalse(_is_easy_apply_card("Promoted Apply on company website"))

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
