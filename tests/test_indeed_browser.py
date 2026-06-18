from __future__ import annotations

import unittest

from cv_job_matcher.sources.indeed_browser import (
    ABSOLUTE_PAGE_SAFETY_LIMIT,
    IndeedBrowserSource,
    _current_start_param,
    _indeed_job_id,
    _normalize_indeed_url,
    _title_has_excluded_keyword,
)


class IndeedBrowserSourceTests(unittest.TestCase):
    def test_normalizes_relative_job_url_to_canonical_viewjob_url(self) -> None:
        self.assertEqual(
            "https://ch.indeed.com/viewjob?jk=abc123",
            _normalize_indeed_url("/rc/clk?jk=abc123&from=vj", "https://ch.indeed.com/jobs"),
        )

    def test_source_id_prefers_data_jk(self) -> None:
        self.assertEqual(
            "data123",
            _indeed_job_id("data123", "https://ch.indeed.com/viewjob?jk=url123", "", ""),
        )

    def test_source_id_reads_jk_from_url(self) -> None:
        self.assertEqual(
            "url123",
            _indeed_job_id(None, "https://ch.indeed.com/viewjob?jk=url123", "", ""),
        )

    def test_source_id_falls_back_to_stable_hash(self) -> None:
        first = _indeed_job_id(None, None, "ML Engineer", "Acme")
        second = _indeed_job_id(None, None, "ML Engineer", "Acme")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("indeed-"))

    def test_excluded_title_keyword_is_case_insensitive_substring(self) -> None:
        self.assertTrue(_title_has_excluded_keyword("Senior Medical Writer", ["writer"]))
        self.assertTrue(_title_has_excluded_keyword("Associate Director", ["director"]))
        self.assertTrue(_title_has_excluded_keyword("Biotech Executive", ["executive"]))
        self.assertTrue(_title_has_excluded_keyword("Junior Quantitative Analyst", ["junior"]))
        self.assertTrue(_title_has_excluded_keyword("Postdoctoral Researcher", ["doctoral"]))
        self.assertTrue(_title_has_excluded_keyword("Post Doctoral Researcher", ["doctoral"]))
        self.assertFalse(_title_has_excluded_keyword("Senior Medical Researcher", ["writer"]))

    def test_current_start_param(self) -> None:
        self.assertEqual(20, _current_start_param("https://ch.indeed.com/jobs?q=ai&start=20"))
        self.assertIsNone(_current_start_param("https://ch.indeed.com/jobs?q=ai"))

    def test_zero_caps_mean_unconfigured_caps(self) -> None:
        source = IndeedBrowserSource(
            "indeed",
            max_results_per_search=0,
            max_pages_per_search=0,
        )
        self.assertEqual(0, source.max_results_per_search)
        self.assertEqual(0, source.max_pages_per_search)
        self.assertGreaterEqual(ABSOLUTE_PAGE_SAFETY_LIMIT, 50)


if __name__ == "__main__":
    unittest.main()
