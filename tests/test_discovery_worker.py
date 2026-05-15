from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db import Database
from app.discovery_worker import DiscoveryWorker
from app.repository import Repository
from app.youtube import InspectionResult


class FakeYouTubeService:
    def __init__(self) -> None:
        self.related_calls: list[str] = []
        self.inspect_calls: list[str] = []

    def discover_related(self, video_id: str) -> list[dict[str, Any]]:
        self.related_calls.append(video_id)
        return [
            {
                "video_id": "dubbed1",
                "title": "Dubbed candidate",
                "channel": "Dub Channel",
                "channel_id": "dubchan",
                "duration_seconds": 120,
                "thumbnail_url": "thumb.jpg",
                "published_at": "2026-04-20",
                "view_count": 100,
            },
            {
                "video_id": "plain1",
                "title": "Plain candidate",
                "channel": "Plain Channel",
                "channel_id": "plainchan",
                "duration_seconds": 120,
                "thumbnail_url": "plain.jpg",
                "published_at": "2026-04-19",
                "view_count": 50,
            },
        ]

    def inspect_video(self, video_id: str) -> InspectionResult:
        self.inspect_calls.append(video_id)
        if video_id == "dubbed1":
            return InspectionResult(
                audio_languages=["en", "es-US"],
                published_at="2026-04-20",
                view_count=100,
                title="Dubbed candidate",
                channel="Dub Channel",
                channel_id="dubchan",
                duration_seconds=120,
                thumbnail_url="thumb.jpg",
            )
        return InspectionResult(
            audio_languages=["en"],
            published_at="2026-04-19",
            view_count=50,
            title="Plain candidate",
            channel="Plain Channel",
            channel_id="plainchan",
            duration_seconds=120,
            thumbnail_url="plain.jpg",
        )


class DiscoveryWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = Settings(project_root=Path(self.temp_dir.name))
        self.repo = Repository(Database(self.settings.db_path))
        self.repo.db.initialize()
        self.youtube = FakeYouTubeService()
        self.worker = DiscoveryWorker(self.repo, self.youtube, self.settings)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_run_once_walks_related_seed_and_publishes_only_dubbed_candidates(self) -> None:
        self.repo.create_discovery_seed(
            seed_kind="related_video",
            source_type="video",
            label="Seed",
            value="seed123",
            priority=10,
        )

        summary = self.worker.run_once(max_seed_discoveries=1, max_candidate_inspections=5)

        self.assertEqual(self.youtube.related_calls, ["seed123"])
        self.assertEqual(set(self.youtube.inspect_calls), {"dubbed1", "plain1"})
        self.assertEqual(summary["related_candidates"], 2)
        self.assertEqual(summary["verified"], 1)
        self.assertEqual(summary["rejected"], 1)
        catalog = self.repo.list_catalog_page(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            page_size=10,
        )
        self.assertEqual([item["video_id"] for item in catalog["items"]], ["dubbed1"])
        frontier = {row["video_id"]: row["state"] for row in self.repo.list_frontier_candidates()}
        self.assertEqual(frontier["dubbed1"], "verified")
        self.assertEqual(frontier["plain1"], "rejected")
        seeds = {(row["source_type"], row["value"]) for row in self.repo.list_discovery_seeds()}
        self.assertIn(("video", "dubbed1"), seeds)


if __name__ == "__main__":
    unittest.main()
