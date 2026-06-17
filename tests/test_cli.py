from __future__ import annotations

import unittest

from cv_job_matcher.cli import render_jobs_html


class CliTests(unittest.TestCase):
    def test_render_jobs_html_highlights_new_jobs(self) -> None:
        html = render_jobs_html(
            [
                {
                    "website": "LinkedIn",
                    "source_id": "123",
                    "title": "Data Scientist",
                    "company": "Example Co",
                    "url": "https://www.linkedin.com/jobs/view/123",
                },
                {
                    "website": "LinkedIn",
                    "source_id": "456",
                    "title": "ML Engineer",
                    "company": "Another Co",
                    "url": "https://www.linkedin.com/jobs/view/456",
                    "status": "applied",
                },
            ],
            {"456"},
        )

        self.assertIn('class="new-job applied-job"', html)
        self.assertIn("data-applied-checkbox", html)
        self.assertIn(" checked>", html)
        self.assertIn('href="https://www.linkedin.com/jobs/view/456"', html)
        self.assertIn("Light blue rows are checked as applied", html)
        self.assertIn("localStorage", html)


if __name__ == "__main__":
    unittest.main()
