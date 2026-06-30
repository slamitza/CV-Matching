from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import unittest

from cv_job_matcher.sources.csv_source import CSVSource


class CSVSourceTests(unittest.TestCase):
    def test_excludes_configured_title_keywords(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "jobs.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
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
                        "source_id": "1",
                        "title": "Linux Software Engineer",
                        "company": "Example Co",
                    }
                )
                writer.writerow(
                    {
                        "source_id": "2",
                        "title": "Software Engineer",
                        "company": "Example Co",
                    }
                )

            source = CSVSource("manual-csv", str(path), exclude_title_keywords=["linux"])

            postings = source.fetch()

            self.assertEqual(1, len(postings))
            self.assertEqual("Software Engineer", postings[0].title)

    def test_excludes_configured_companies(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "jobs.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
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
                        "source_id": "1",
                        "title": "Data Scientist",
                        "company": "Crossing Hurdles",
                    }
                )
                writer.writerow(
                    {
                        "source_id": "2",
                        "title": "Software Engineer",
                        "company": "Example Co",
                    }
                )

            source = CSVSource(
                "manual-csv",
                str(path),
                exclude_companies=["crossing hurdles"],
            )

            postings = source.fetch()

            self.assertEqual(1, len(postings))
            self.assertEqual("Example Co", postings[0].company)


if __name__ == "__main__":
    unittest.main()
