from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.desktop_services import prepare_runtime_storage


class StorageTests(unittest.TestCase):
    def test_prepare_runtime_storage_migrates_legacy_bundle_data_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime_data_dir = root / "runtime" / "data"
            legacy_data_dir = root / "bundle" / "data"
            legacy_data_dir.mkdir(parents=True)
            legacy_db = legacy_data_dir / "dub_index_desktop.db"
            legacy_db.write_text("legacy-db", encoding="utf-8")

            settings = SimpleNamespace(
                data_dir=runtime_data_dir,
                db_path=runtime_data_dir / "dub_index_desktop.db",
                legacy_bundle_data_dir=legacy_data_dir,
            )

            prepare_runtime_storage(settings)

            self.assertTrue(settings.db_path.exists())
            self.assertEqual(settings.db_path.read_text(encoding="utf-8"), "legacy-db")

            settings.db_path.write_text("current-db", encoding="utf-8")
            legacy_db.write_text("legacy-db-updated", encoding="utf-8")
            prepare_runtime_storage(settings)

            self.assertEqual(settings.db_path.read_text(encoding="utf-8"), "current-db")


if __name__ == "__main__":
    unittest.main()
