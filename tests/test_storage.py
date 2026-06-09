from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from app.config import get_settings
from app.desktop_services import prepare_runtime_storage


class StorageTests(unittest.TestCase):
    def test_starter_pack_contains_strict_spanish_dub_evidence(self) -> None:
        starter_path = get_settings().starter_pack_path
        self.assertTrue(starter_path.exists())

        with sqlite3.connect(starter_path) as conn:
            track_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(video_audio_tracks)")
            }
            self.assertIn("is_original_audio", track_columns)

            strict_spanish_count = conn.execute(
                """
                SELECT COUNT(DISTINCT v.video_id)
                FROM videos v
                JOIN video_audio_tracks t ON t.video_id = v.video_id
                WHERE v.has_dubbing = 1
                  AND v.published_at IS NOT NULL
                  AND LOWER(t.language_code) LIKE 'es%'
                  AND t.is_original_audio = 0
                """
            ).fetchone()[0]

        self.assertGreaterEqual(strict_spanish_count, 100)

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

    def test_prepare_runtime_storage_migrates_old_appdata_database_to_portable_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            portable_data_dir = root / "dist" / "YouTubeDubIndexer" / "data"
            old_appdata_data_dir = root / "localappdata" / "YouTubeDubIndexer" / "data"
            old_appdata_data_dir.mkdir(parents=True)
            old_db = old_appdata_data_dir / "dub_index_desktop.db"
            old_db.write_text("old-appdata-db", encoding="utf-8")

            settings = SimpleNamespace(
                data_dir=portable_data_dir,
                db_path=portable_data_dir / "dub_index_desktop.db",
                legacy_bundle_data_dir=portable_data_dir,
                legacy_appdata_data_dir=old_appdata_data_dir,
            )

            prepare_runtime_storage(settings)

            self.assertTrue(settings.db_path.exists())
            self.assertEqual(settings.db_path.read_text(encoding="utf-8"), "old-appdata-db")


if __name__ == "__main__":
    unittest.main()
