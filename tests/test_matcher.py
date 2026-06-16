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


if __name__ == "__main__":
    unittest.main()
