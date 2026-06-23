from __future__ import annotations

import unittest

from cv_job_matcher.dashboard import render_dashboard


class DashboardTests(unittest.TestCase):
    def test_render_dashboard_has_open_applied_and_discarded_views(self) -> None:
        html = render_dashboard(
            [
                {
                    "id": 1,
                    "website": "LinkedIn",
                    "source_id": "123",
                    "title": "Data Scientist",
                    "company": "Example Co",
                    "location": "Zurich",
                    "url": "https://www.linkedin.com/jobs/view/123/",
                    "seen_count": 1,
                    "last_seen_at": "2026-06-23T10:00:00Z",
                    "status": "new",
                },
                {
                    "id": 2,
                    "website": "Indeed",
                    "source_id": "abc",
                    "title": "ML Engineer",
                    "company": "Another Co",
                    "location": "Zurich",
                    "url": "https://ch.indeed.com/viewjob?jk=abc",
                    "seen_count": 2,
                    "last_seen_at": "2026-06-23T10:00:00Z",
                    "status": "applied",
                },
                {
                    "id": 3,
                    "website": "LinkedIn",
                    "source_id": "456",
                    "title": "Head of Data",
                    "company": "Discard Co",
                    "location": "Zurich",
                    "url": "https://www.linkedin.com/jobs/view/456/",
                    "seen_count": 1,
                    "last_seen_at": "2026-06-23T10:00:00Z",
                    "status": "discarded",
                },
            ]
        )

        self.assertIn("Open Jobs", html)
        self.assertIn("Applied", html)
        self.assertIn("Discarded", html)
        self.assertIn("applied-icon", html)
        self.assertIn("discarded-icon", html)
        self.assertIn('data-table-body="open"', html)
        self.assertIn('data-table-body="applied"', html)
        self.assertIn('data-table-body="discarded"', html)
        self.assertIn('data-target-status="applied"', html)
        self.assertIn('data-target-status="discarded"', html)
        self.assertIn('data-target-status="new"', html)
        self.assertIn("selectedTab()", html)
        self.assertIn("syncEmptyRows()", html)
        self.assertNotIn("showTab(targetView)", html)
        self.assertIn("/jobs/${jobId}/status", html)


if __name__ == "__main__":
    unittest.main()
