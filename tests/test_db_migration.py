from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db import Database


class DatabaseMigrationTests(unittest.TestCase):
    def test_initialize_adds_new_video_columns_to_legacy_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.db"
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE videos (
                    video_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    channel TEXT,
                    channel_id TEXT,
                    duration_seconds INTEGER,
                    thumbnail_url TEXT,
                    has_dubbing INTEGER,
                    audio_languages_json TEXT,
                    audio_language_count INTEGER,
                    last_seen_at TEXT NOT NULL,
                    last_checked_at TEXT,
                    inspect_status TEXT NOT NULL DEFAULT 'pending',
                    inspect_error TEXT
                );
                """
            )
            conn.commit()
            conn.close()

            db = Database(db_path)
            db.initialize()

            check = sqlite3.connect(db_path)
            columns = {
                row[1]
                for row in check.execute("PRAGMA table_info(videos)").fetchall()
            }
            check.close()

            self.assertIn("published_at", columns)
            self.assertIn("view_count", columns)
            self.assertIn("is_favorite", columns)
            self.assertIn("dub_kind", columns)
            self.assertIn("dub_classifier_version", columns)

    def test_initialize_downgrades_legacy_automatic_without_spanish_track_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy_auto.db"
            db = Database(db_path)
            db.initialize()

            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                INSERT INTO videos (
                    video_id, title, channel, published_at, dub_kind, has_dubbing,
                    audio_languages_json, audio_language_count, last_seen_at, inspect_status
                )
                VALUES (
                    'auto1', 'Auto', 'Chan', '2026-04-20', 'automatic', 1,
                    '["ar", "bn", "de", "en", "es", "fr", "hi", "id"]', 8,
                    '2026-04-20T00:00:00+00:00', 'ok'
                )
                """
            )
            conn.execute("DELETE FROM app_preferences WHERE key = 'dub_kind_classifier_v2'")
            conn.execute("DELETE FROM app_preferences WHERE key = 'dub_kind_classifier_v5_spanish_track_evidence'")
            conn.commit()
            conn.close()

            db.initialize()

            check = sqlite3.connect(db_path)
            dub_kind = check.execute("SELECT dub_kind FROM videos WHERE video_id = 'auto1'").fetchone()[0]
            preference = check.execute(
                "SELECT value FROM app_preferences WHERE key = 'dub_kind_classifier_v5_spanish_track_evidence'"
            ).fetchone()[0]
            check.close()

            self.assertEqual(dub_kind, "manual")
            self.assertEqual(preference, "1")

    def test_initialize_preserves_automatic_with_spanish_track_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy_auto_v2.db"
            db = Database(db_path)
            db.initialize()

            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                INSERT INTO videos (
                    video_id, title, channel, published_at, dub_kind, dub_evidence_json, has_dubbing,
                    audio_languages_json, audio_language_count, last_seen_at, inspect_status
                )
                VALUES (
                    'auto1', 'Auto', 'Chan', '2026-04-20', 'automatic',
                    '{"auto_dubbed_languages":["es"]}', 1,
                    '["ar", "bn", "de", "en", "es", "fr", "hi", "id"]', 8,
                    '2026-04-20T00:00:00+00:00', 'ok'
                )
                """
            )
            conn.execute("INSERT OR REPLACE INTO app_preferences(key, value) VALUES('dub_kind_classifier_v2', '1')")
            conn.execute("DELETE FROM app_preferences WHERE key = 'dub_kind_classifier_v3'")
            conn.execute("DELETE FROM app_preferences WHERE key = 'dub_kind_classifier_v5_spanish_track_evidence'")
            conn.commit()
            conn.close()

            db.initialize()

            check = sqlite3.connect(db_path)
            dub_kind = check.execute("SELECT dub_kind FROM videos WHERE video_id = 'auto1'").fetchone()[0]
            track_flag = check.execute(
                "SELECT is_auto_dubbed FROM video_audio_tracks WHERE video_id = 'auto1' AND language_code = 'es'"
            ).fetchone()[0]
            check.close()

            self.assertEqual(dub_kind, "automatic")
            self.assertEqual(track_flag, 1)

    def test_initialize_adds_original_audio_column_to_legacy_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy_tracks.db"
            db = Database(db_path)
            db.initialize()

            conn = sqlite3.connect(db_path)
            conn.execute("ALTER TABLE video_audio_tracks RENAME TO video_audio_tracks_old")
            conn.execute(
                """
                CREATE TABLE video_audio_tracks (
                    video_id TEXT NOT NULL,
                    language_code TEXT NOT NULL,
                    language_base TEXT NOT NULL,
                    track_id TEXT NOT NULL DEFAULT '',
                    is_auto_dubbed INTEGER,
                    evidence_source TEXT NOT NULL DEFAULT 'stored',
                    PRIMARY KEY (video_id, language_code, track_id)
                )
                """
            )
            conn.execute("DROP TABLE video_audio_tracks_old")
            conn.commit()
            conn.close()

            db.initialize()

            check = sqlite3.connect(db_path)
            columns = {
                row[1]
                for row in check.execute("PRAGMA table_info(video_audio_tracks)").fetchall()
            }
            check.close()

            self.assertIn("is_original_audio", columns)


if __name__ == "__main__":
    unittest.main()
