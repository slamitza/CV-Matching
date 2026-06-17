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
            self.assertEqual("job-1", jobs[0]["source_id"])
            self.assertEqual(2, jobs[0]["seen_count"])

            database.record_application(int(jobs[0]["id"]), notes="Applied online")
            applications = database.list_applications()
            self.assertEqual(1, len(applications))
            self.assertEqual("applied", applications[0]["status"])

    def test_latest_scan_new_jobs_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "jobs.sqlite3")
            database.init()

            scan_id = database.start_scan("linkedin-browser")
            new_job = JobPosting(
                source="linkedin-browser",
                source_id="123",
                title="Data Scientist",
                company="Example Co",
                url="https://www.linkedin.com/jobs/view/123",
            )
            match = MatchResult(score=0, matched_keywords=[], missing_keywords=[])
            self.assertTrue(database.upsert_job(new_job, match))
            self.assertFalse(database.upsert_job(new_job, match))

            another_new_job = JobPosting(
                source="linkedin-browser",
                source_id="456",
                title="ML Engineer",
                company="Another Co",
                url="https://www.linkedin.com/jobs/view/456",
            )
            self.assertTrue(database.upsert_job(another_new_job, match))
            database.finish_scan(scan_id, found_count=2, new_count=1, updated_count=1)

            rows = database.list_new_jobs_from_latest_scan(source="linkedin-browser")
            self.assertEqual(1, len(rows))
            self.assertEqual("LinkedIn", rows[0]["website"])
            self.assertEqual("456", rows[0]["source_id"])
            self.assertEqual("ML Engineer", rows[0]["title"])
            self.assertEqual("Another Co", rows[0]["company"])
            self.assertEqual("https://www.linkedin.com/jobs/view/456", rows[0]["url"])

            all_rows = database.list_jobs(source="linkedin-browser")
            self.assertEqual("LinkedIn", all_rows[0]["website"])


if __name__ == "__main__":
    unittest.main()
