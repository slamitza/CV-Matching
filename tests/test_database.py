from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cv_job_matcher.database import Database
from cv_job_matcher.models import JobPosting, MatchResult


class DatabaseTests(unittest.TestCase):
    def test_upsert_and_application_tracking(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "jobs.sqlite3")
            database.init()

            job = JobPosting(
                source="test",
                source_id="job-1",
                title="Python Developer",
                company="Example Co",
                url="https://example.com/jobs/1",
            )
            match = MatchResult(score=88.0, matched_keywords=["python"], missing_keywords=[])

            self.assertTrue(database.upsert_job(job, match))
            self.assertFalse(database.upsert_job(job, match))

            jobs = database.list_jobs(min_score=0)
            self.assertEqual(1, len(jobs))
            self.assertEqual("Example Co", jobs[0]["company"])

            database.record_application(int(jobs[0]["id"]), notes="Applied online")
            applications = database.list_applications()
            self.assertEqual(1, len(applications))
            self.assertEqual("applied", applications[0]["status"])


if __name__ == "__main__":
    unittest.main()
