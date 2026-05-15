from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.perf.generate_synthetic_db import build


class PerfHarnessTests(unittest.TestCase):
    def test_synthetic_db_builder_commits_chunks_and_reports_json_progress(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            db_path = Path(temp_dir) / "synthetic.db"
            events: list[dict[str, object]] = []

            summary = build(db_path, rows=120, sources=3, chunk_size=50, progress=events.append)

            self.assertEqual(summary["rows"], 120)
            self.assertEqual(summary["chunks"], 3)
            self.assertTrue(db_path.exists())
            self.assertEqual([event["rows"] for event in events], [50, 100, 120])
            json.dumps(summary)
            for event in events:
                json.dumps(event)


if __name__ == "__main__":
    unittest.main()
