from __future__ import annotations

import unittest

from cv_job_matcher.config import SourceConfig
from cv_job_matcher.scanner import _source_batches_by_site


class ScannerTests(unittest.TestCase):
    def test_parallel_batches_do_not_repeat_same_site(self) -> None:
        batches = _source_batches_by_site(
            [
                SourceConfig(name="linkedin-a", type="linkedin_browser"),
                SourceConfig(name="indeed", type="indeed_browser"),
                SourceConfig(name="linkedin-b", type="linkedin_browser"),
            ]
        )

        self.assertEqual(
            [["linkedin-a", "indeed"], ["linkedin-b"]],
            [[source.name for source in batch] for batch in batches],
        )


if __name__ == "__main__":
    unittest.main()
