from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.db import Database
from app.repository import CandidateVideo, Repository, SourceInput, to_iso
from app.run_manager import RunManager
from app.youtube import InspectionResult


class FakeYouTubeService:
    def discover_source(self, source: dict[str, object]) -> list[dict[str, object]]:
        value = str(source["value"])
        if "broken" in value:
            raise ValueError("invalid source")
        return [
            {
                "video_id": "abc123",
                "title": "Demo video",
                "channel": "Demo channel",
                "channel_id": "chan1",
                "duration_seconds": 123,
                "thumbnail_url": None,
            }
        ]

    def inspect_video(self, video_id: str) -> InspectionResult:
        return InspectionResult(audio_languages=["en", "es-419"])


class MetadataYouTubeService(FakeYouTubeService):
    def discover_source(self, source: dict[str, object]) -> list[dict[str, object]]:
        return []

    def inspect_video(self, video_id: str) -> InspectionResult:
        if video_id == "plain1":
            return InspectionResult(audio_languages=["es-419"], published_at="2026-04-19", view_count=24)
        return InspectionResult(audio_languages=["en", "es-419"], published_at="2026-04-20", view_count=42)


class RunManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.db"
        self.repo = Repository(Database(db_path))
        self.repo.db.initialize()
        self.settings = SimpleNamespace(
            inspect_stale_days=30,
            inspect_workers=1,
            inspect_retry_attempts=0,
            metadata_backfill_limit=50,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_run_all_continues_when_one_source_fails(self) -> None:
        self.repo.create_source(SourceInput("channel", "Broken", "broken-source", 5, True))
        self.repo.create_source(
            SourceInput("channel", "Working", "https://www.youtube.com/@kurzgesagt/videos", 5, True)
        )
        manager = RunManager(self.repo, FakeYouTubeService(), self.settings)

        run_id = self.repo.create_run("all")
        self.repo.mark_run_running(run_id)
        warning = manager._execute(run_id, None)
        self.repo.finish_run(run_id, status="completed", error=warning)

        run = self.repo.get_run(run_id)
        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["candidates_found"], 1)
        self.assertEqual(run["videos_checked"], 1)
        self.assertEqual(run["dubbed_found"], 1)
        self.assertIn("Broken", run["error"])

    def test_metadata_backfill_rechecks_existing_reviewed_videos_missing_dates(self) -> None:
        source_id = self.repo.create_source(SourceInput("channel", "Saved", "saved-source", 5, True))
        self.repo.upsert_candidate(
            CandidateVideo("legacy1", "Legacy", "Chan", "chan1", 100, None, source_id, to_iso())
        )
        self.repo.upsert_candidate(
            CandidateVideo("plain1", "Plain", "Chan", "chan1", 100, None, source_id, to_iso())
        )
        self.repo.store_inspection_result(
            "legacy1",
            audio_languages=["en", "es-419"],
            has_dubbing=True,
            published_at=None,
            view_count=None,
        )
        self.repo.store_inspection_result(
            "plain1",
            audio_languages=["es-419"],
            has_dubbing=False,
            published_at=None,
            view_count=None,
        )
        manager = RunManager(self.repo, MetadataYouTubeService(), self.settings)

        run_id = self.repo.create_run("all")
        self.repo.mark_run_running(run_id)
        manager._execute(run_id, None)
        self.repo.finish_run(run_id, status="completed")

        catalog = self.repo.list_catalog(lang=None, source_id=None, channel=None, query=None, only_dubbed=False)
        rows = {row["video_id"]: row for row in catalog}
        self.assertEqual(rows["legacy1"]["published_at"], "2026-04-20")
        self.assertEqual(rows["legacy1"]["view_count"], 42)
        self.assertEqual(rows["plain1"]["published_at"], "2026-04-19")
        self.assertEqual(rows["plain1"]["view_count"], 24)
        run = self.repo.get_run(run_id)
        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run["videos_checked"], 2)

    def test_progress_events_are_cumulative_every_fifty_inspections(self) -> None:
        manager = RunManager(self.repo, MetadataYouTubeService(), self.settings)
        events: list[dict[str, object]] = []
        manager.set_event_callback(events.append)
        run_id = self.repo.create_run("metadata")
        self.repo.mark_run_running(run_id)
        video_ids = {f"vid{index:08d}" for index in range(120)}
        source_id = self.repo.create_source(SourceInput("search", "Progress", "progress", 120, True))
        for video_id in video_ids:
            self.repo.upsert_candidate(
                CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso())
            )

        manager._inspect_video_ids(run_id, video_ids)

        progress_events = [event for event in events if event.get("event") == "run_progress"]
        self.assertEqual([event["videos_checked"] for event in progress_events], [50, 100, 120])
        self.assertEqual([event["candidates_found"] for event in progress_events], [120, 120, 120])


if __name__ == "__main__":
    unittest.main()
