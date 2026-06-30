from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import unittest

from cv_job_matcher.config import Settings, SourceConfig
from cv_job_matcher.database import Database
from cv_job_matcher.scanner import _source_batches_by_site, scan


class ScannerTests(unittest.TestCase):
    def test_parallel_batches_use_source_names(self) -> None:
        batches = _source_batches_by_site(
            [
                SourceConfig(name="remote-python", type="remotive"),
                SourceConfig(name="manual-csv", type="csv"),
                SourceConfig(name="rss-example", type="rss"),
            ]
        )

        self.assertEqual(
            [["remote-python", "manual-csv", "rss-example"]],
            [[source.name for source in batch] for batch in batches],
        )

    def test_scan_skips_excluded_companies(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "jobs.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "source_id",
                        "title",
                        "company",
                        "location",
                        "url",
                        "description",
                        "posted_at",
                        "remote",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "source_id": "blocked",
                        "title": "Data Scientist",
                        "company": "Crossing Hurdles",
                    }
                )
                writer.writerow(
                    {
                        "source_id": "kept",
                        "title": "Software Engineer",
                        "company": "Example Co",
                    }
                )
            settings = Settings(
                database_path=root / "jobs.sqlite3",
                cv_path=root / "cv.txt",
                score_jobs=False,
                minimum_score=0,
                search_terms=[],
                excluded_companies=["Crossing Hurdles"],
                required_keywords=[],
                sources=[
                    SourceConfig(
                        name="manual-csv",
                        type="csv",
                        options={"path": str(csv_path)},
                    )
                ],
            )

            summaries = scan(settings)

            database = Database(settings.database_path)
            rows = database.list_jobs(limit=10)
            self.assertEqual(1, len(rows))
            self.assertEqual("kept", rows[0]["source_id"])
            self.assertEqual(1, summaries[0].found_count)


if __name__ == "__main__":
    unittest.main()
