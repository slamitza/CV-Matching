from __future__ import annotations

import unittest

from cv_job_matcher.matcher import build_profile, score_job
from cv_job_matcher.models import JobPosting


class MatcherTests(unittest.TestCase):
    def test_required_keywords_drive_score(self) -> None:
        profile = build_profile(
            "Python engineer with SQL automation and backend API experience.",
            required_keywords=["python", "sql", "automation"],
        )
        job = JobPosting(
            source="test",
            source_id="1",
            title="Python Automation Engineer",
            company="Example Co",
            description="Build backend services with SQL and APIs.",
        )

        result = score_job(profile, job)

        self.assertGreaterEqual(result.score, 70)
        self.assertIn("python", result.matched_keywords)
        self.assertEqual([], result.missing_keywords)

    def test_ai_and_ml_are_kept_as_keywords(self) -> None:
        profile = build_profile(
            "AI engineer with ML, Python, statistics, and bioinformatics experience.",
            required_keywords=["ai", "ml", "python", "bioinformatics"],
        )
        job = JobPosting(
            source="test",
            source_id="2",
            title="AI / ML Engineer",
            company="Example Co",
            description="Python role supporting bioinformatics models.",
        )

        result = score_job(profile, job)

        self.assertIn("ai", result.matched_keywords)
        self.assertIn("ml", result.matched_keywords)
        self.assertEqual([], result.missing_keywords)


if __name__ == "__main__":
    unittest.main()
