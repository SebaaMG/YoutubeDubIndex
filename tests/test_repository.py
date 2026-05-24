from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from app.db import Database
from app.repository import (
    CURRENT_DUB_CLASSIFIER_VERSION,
    SPANISH_LANGUAGE_CODES,
    SPANISH_LANGUAGE_FILTER,
    CandidateVideo,
    Repository,
    SourceInput,
    to_iso,
    utc_now,
)


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.db"
        self.repo = Repository(Database(db_path))
        self.repo.db.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_deduplicates_video_and_keeps_source_links(self) -> None:
        source_a = self.repo.create_source(SourceInput("search", "A", "mark rober", 5))
        source_b = self.repo.create_source(SourceInput("search", "B", "mrbeast", 5))

        candidate_a = CandidateVideo("abc123", "Video", "Chan", "chan1", 123, None, source_a, to_iso())
        candidate_b = CandidateVideo("abc123", "Video", "Chan", "chan1", 123, None, source_b, to_iso())
        self.repo.upsert_candidate(candidate_a)
        self.repo.upsert_candidate(candidate_b)
        self.repo.store_inspection_result(
            "abc123",
            audio_languages=["en"],
            has_dubbing=False,
            published_at="2026-04-20",
            view_count=1,
        )

        catalog = self.repo.list_catalog(lang=None, source_id=None, channel=None, query=None, only_dubbed=False)
        self.assertEqual(len(catalog), 1)

    def test_catalog_hides_unreviewed_failed_and_missing_date_videos(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        for video_id in ("pending1", "failed1", "missing_date1", "ready1"):
            candidate = CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso())
            self.repo.upsert_candidate(candidate)

        self.repo.store_inspection_failure("failed1", "network error")
        self.repo.store_inspection_result(
            "missing_date1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at=None,
            view_count=100,
        )
        self.repo.store_inspection_result(
            "ready1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=100,
        )

        catalog = self.repo.list_catalog(lang=None, source_id=None, channel=None, query=None, only_dubbed=False)
        self.assertEqual([item["video_id"] for item in catalog], ["ready1"])

    def test_catalog_filters_only_dubbed_by_default(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "mark rober", 5))
        candidate = CandidateVideo("abc123", "Video", "Chan", "chan1", 123, None, source_id, to_iso())
        self.repo.upsert_candidate(candidate)
        self.repo.store_inspection_result(
            "abc123",
            audio_languages=["en", "es-419"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=100,
        )

        hidden = CandidateVideo("def456", "Plain", "Chan", "chan1", 123, None, source_id, to_iso())
        self.repo.upsert_candidate(hidden)
        self.repo.store_inspection_result(
            "def456",
            audio_languages=["en"],
            has_dubbing=False,
            published_at="2026-04-19",
            view_count=50,
        )

        dubbed_only = self.repo.list_catalog(lang=None, source_id=None, channel=None, query=None, only_dubbed=True)
        all_items = self.repo.list_catalog(lang=None, source_id=None, channel=None, query=None, only_dubbed=False)
        self.assertEqual(len(dubbed_only), 1)
        self.assertEqual(len(all_items), 2)

    def test_dashboard_dubbed_videos_matches_default_discover_count(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 10))

        def add_result(
            video_id: str,
            audio_languages: list[str],
            *,
            published_at: str | None,
            view_count: int | None,
        ) -> None:
            self.repo.upsert_candidate(
                CandidateVideo(
                    video_id,
                    f"Title {video_id}",
                    "Stats Channel",
                    "stats-channel",
                    100,
                    None,
                    source_id,
                    to_iso(),
                )
            )
            self.repo.store_inspection_result(
                video_id,
                audio_languages=audio_languages,
                has_dubbing=True,
                dub_evidence={
                    "source": "inspection",
                    "original_audio_languages": ["en"],
                    "auto_dubbed_languages": [],
                },
                published_at=published_at,
                view_count=view_count,
            )

        add_result("spanish-ready", ["en", "es-US"], published_at="2026-04-20", view_count=100)
        add_result("french-only", ["en", "fr"], published_at="2026-04-21", view_count=100)
        add_result("spanish-missing-date", ["en", "es-US"], published_at=None, view_count=100)
        add_result("spanish-missing-views", ["en", "es-US"], published_at="2026-04-22", view_count=None)

        default_discover_count = self.repo.count_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        stats = self.repo.dashboard_stats()

        self.assertEqual(default_discover_count, 1)
        self.assertEqual(stats["dubbed_videos"], default_discover_count)

    def test_catalog_can_sort_by_views_and_filter_by_year(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))

        old_video = CandidateVideo("old1", "Old video", "Chan", "chan1", 100, None, source_id, to_iso())
        new_video = CandidateVideo("new1", "New video", "Chan", "chan1", 100, None, source_id, to_iso())
        self.repo.upsert_candidate(old_video)
        self.repo.upsert_candidate(new_video)
        self.repo.store_inspection_result(
            "old1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at="2021-05-14",
            view_count=50,
        )
        self.repo.store_inspection_result(
            "new1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at="2024-01-02",
            view_count=500,
        )

        by_views = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            sort_by="views",
        )
        self.assertEqual([item["video_id"] for item in by_views], ["new1", "old1"])

        random_items = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            sort_by="random",
        )
        self.assertEqual({item["video_id"] for item in random_items}, {"new1", "old1"})

        only_2021 = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            year=2021,
        )
        self.assertEqual([item["video_id"] for item in only_2021], ["old1"])

        after_2022 = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            year_after=2022,
        )
        self.assertEqual([item["video_id"] for item in after_2022], ["new1"])

    def test_needs_inspection_when_legacy_video_is_missing_published_at(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        candidate = CandidateVideo("legacy1", "Legacy video", "Chan", "chan1", 100, None, source_id, to_iso())
        self.repo.upsert_candidate(candidate)
        self.repo.store_inspection_result(
            "legacy1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at=None,
            view_count=None,
        )

        self.assertTrue(self.repo.needs_inspection("legacy1", stale_days=30))

    def test_needs_inspection_when_dub_classifier_version_is_stale(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        candidate = CandidateVideo("stale1", "Stale classifier", "Chan", "chan1", 100, None, source_id, to_iso())
        self.repo.upsert_candidate(candidate)
        self.repo.store_inspection_result(
            "stale1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=100,
            classifier_version=3,
        )

        self.assertTrue(self.repo.needs_inspection("stale1", stale_days=30, classifier_version=4))
        self.assertIn(
            "stale1",
            self.repo.list_video_ids_missing_metadata(limit=10, classifier_version=4),
        )

    def test_lists_reviewed_videos_missing_upload_metadata(self) -> None:
        source_a = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        source_b = self.repo.create_source(SourceInput("search", "B", "other", 5))

        missing = CandidateVideo("missing1", "Missing date", "Chan", "chan1", 100, None, source_a, to_iso())
        complete = CandidateVideo("complete1", "Complete date", "Chan", "chan1", 100, None, source_a, to_iso())
        other_source = CandidateVideo("other1", "Other source", "Chan", "chan1", 100, None, source_b, to_iso())
        plain = CandidateVideo("plain1", "Plain", "Chan", "chan1", 100, None, source_a, to_iso())
        for candidate in (missing, complete, other_source, plain):
            self.repo.upsert_candidate(candidate)

        self.repo.store_inspection_result(
            "missing1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at=None,
            view_count=None,
        )
        self.repo.store_inspection_result(
            "complete1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at="2026-04-22",
            view_count=100,
        )
        self.repo.store_inspection_result(
            "other1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at=None,
            view_count=None,
        )
        self.repo.store_inspection_result(
            "plain1",
            audio_languages=["en"],
            has_dubbing=False,
            published_at=None,
            view_count=None,
        )

        self.assertEqual(set(self.repo.list_video_ids_missing_metadata()), {"missing1", "complete1", "other1", "plain1"})
        self.assertEqual(set(self.repo.list_video_ids_missing_metadata(source_id=source_a)), {"missing1", "complete1", "plain1"})

    def test_upsert_candidate_preserves_discovery_metadata(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        candidate = CandidateVideo(
            "meta1",
            "Metadata from search",
            "Chan",
            "chan1",
            100,
            None,
            source_id,
            to_iso(),
            published_at="2026-04-20",
            view_count=123,
        )
        self.repo.upsert_candidate(candidate)
        self.repo.store_inspection_result(
            "meta1",
            audio_languages=["en"],
            has_dubbing=False,
            published_at=None,
            view_count=None,
        )

        catalog = self.repo.list_catalog(lang=None, source_id=None, channel=None, query=None, only_dubbed=False)
        self.assertEqual(catalog[0]["published_at"], "2026-04-20")
        self.assertEqual(catalog[0]["view_count"], 123)

    def test_inspection_backfills_channel_metadata(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo("channel1", "Original title", None, None, None, None, source_id, to_iso())
        )

        self.repo.store_inspection_result(
            "channel1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=123,
            title="Better title",
            channel="Real Channel",
            channel_id="real-channel-id",
            duration_seconds=42,
            thumbnail_url="thumb.jpg",
        )

        catalog = self.repo.list_catalog(lang=None, source_id=None, channel=None, query=None, only_dubbed=False)
        self.assertEqual(catalog[0]["title"], "Better title")
        self.assertEqual(catalog[0]["channel"], "Real Channel")
        self.assertEqual(catalog[0]["channel_id"], "real-channel-id")
        self.assertEqual(catalog[0]["duration_seconds"], 42)
        self.assertEqual(catalog[0]["thumbnail_url"], "thumb.jpg")

    def test_catalog_groups_spanish_language_filters(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        videos = {
            "esus": ["en", "es-US"],
            "eses": ["en", "es-ES"],
            "es419": ["en", "es-419"],
            "esplain": ["en", "es"],
            "fr": ["en", "fr-FR"],
        }

        for video_id, languages in videos.items():
            candidate = CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso())
            self.repo.upsert_candidate(candidate)
            self.repo.store_inspection_result(
                video_id,
                audio_languages=languages,
                has_dubbing=True,
                dub_evidence={
                    "source": "inspection",
                    "languages": languages,
                    "original_audio_languages": ["en"],
                    "auto_dubbed_languages": [],
                },
                published_at="2026-04-20",
                view_count=100,
            )

        filters = self.repo.list_catalog_filters()
        self.assertIn(SPANISH_LANGUAGE_FILTER, filters["languages"])
        for lang in SPANISH_LANGUAGE_CODES:
            self.assertNotIn(lang, filters["languages"])
        self.assertIn("fr-FR", filters["languages"])

        spanish_items = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        self.assertEqual({item["video_id"] for item in spanish_items}, {"esus", "eses", "es419", "esplain"})

    def test_catalog_can_filter_favorites(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        for video_id in ("fav1", "plain1"):
            candidate = CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso())
            self.repo.upsert_candidate(candidate)
            self.repo.store_inspection_result(
                video_id,
                audio_languages=["en", "es-US"],
                has_dubbing=True,
                published_at="2026-04-20",
                view_count=100,
            )

        self.repo.set_video_favorite("fav1", True)

        favorites = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            only_favorites=True,
        )
        self.assertEqual([item["video_id"] for item in favorites], ["fav1"])
        self.assertEqual(favorites[0]["is_favorite"], 1)

    def test_catalog_can_filter_manual_and_automatic_dubs(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        for video_id, dub_kind in (("manual1", "manual"), ("auto1", "automatic")):
            candidate = CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso())
            self.repo.upsert_candidate(candidate)
            self.repo.store_inspection_result(
                video_id,
                audio_languages=["en", "es-US"],
                has_dubbing=True,
                dub_kind=dub_kind,
                dub_evidence=(
                    {"source": "inspection", "auto_dubbed_languages": ["es-US"], "original_audio_languages": ["en"]}
                    if dub_kind == "automatic"
                    else {"source": "inspection", "auto_dubbed_languages": [], "original_audio_languages": ["en"]}
                ),
                published_at="2026-04-20",
                view_count=100,
            )

        manual = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
        )
        automatic = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="automatic",
        )

        self.assertEqual([item["video_id"] for item in manual], ["manual1"])
        self.assertEqual([item["video_id"] for item in automatic], ["auto1"])

    def test_spanish_unknown_original_tracks_are_hidden_and_prioritized_for_recheck(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(CandidateVideo("unknown1", "Unknown", "Chan", "chan1", 100, None, source_id, to_iso()))
        self.repo.store_inspection_result(
            "unknown1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "legacy", "languages": ["en", "es-US"]},
            published_at="2026-04-20",
            view_count=100,
        )

        catalog = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        missing = self.repo.list_video_ids_missing_metadata(limit=10)

        self.assertEqual(catalog, [])
        self.assertIn("unknown1", missing)

    def test_bad_metadata_is_marked_incomplete_for_ytdlp_repair(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo(
                "zRtGL0-5rg4",
                "zRtGL0-5rg4",
                "Last To Leave Grocery Store, Wins $250,000",
                "chan1",
                100,
                None,
                source_id,
                to_iso(),
            )
        )
        self.repo.store_inspection_result(
            "zRtGL0-5rg4",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_kind="automatic",
            dub_evidence={"source": "legacy", "auto_dubbed_languages": ["es-US"]},
            title="zRtGL0-5rg4",
            channel="Last To Leave Grocery Store, Wins $250,000",
            published_at="2026-04-20",
            view_count=100,
        )

        missing = self.repo.list_video_ids_missing_metadata(limit=10)

        self.assertIn("zRtGL0-5rg4", missing)

    def test_catalog_hides_dubbed_video_until_display_metadata_is_repaired(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo(
                "82Zi7ZrHeY8",
                "82Zi7ZrHeY8",
                "I Tried Exotic Food On Facebook Marketplace!",
                None,
                None,
                None,
                source_id,
                to_iso(),
            )
        )
        self.repo.store_inspection_result(
            "82Zi7ZrHeY8",
            audio_languages=["en", "es"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"]},
            title="82Zi7ZrHeY8",
            channel="I Tried Exotic Food On Facebook Marketplace!",
            published_at="2026-05-14",
            view_count=100,
        )

        catalog = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )

        self.assertEqual(catalog, [])

    def test_any_youtube_id_like_title_is_incomplete_even_if_not_current_video_id(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo("abc123def45", "Placeholder", "Real Channel", "chan1", 100, None, source_id, to_iso())
        )
        self.repo.store_inspection_result(
            "abc123def45",
            audio_languages=["en", "es"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"]},
            title="ZZZyyyXXX11",
            channel="Real Channel",
            published_at="2026-05-14",
            view_count=100,
        )

        with self.repo.db.connect() as conn:
            row = conn.execute(
                "SELECT metadata_complete FROM videos WHERE video_id = ?",
                ("abc123def45",),
            ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["metadata_complete"], 0)

    def test_inspection_repairs_frontier_metadata_placeholders(self) -> None:
        self.repo.enqueue_candidate(
            {
                "video_id": "82Zi7ZrHeY8",
                "title": "82Zi7ZrHeY8",
                "channel": "I Tried Exotic Food On Facebook Marketplace!",
            },
            priority=90,
        )

        self.repo.store_inspection_result(
            "82Zi7ZrHeY8",
            audio_languages=["en", "es"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"]},
            title="I Tried Exotic Food On Facebook Marketplace!",
            channel="Nick Kratka",
            channel_id="UCRPNk3TA5cbyB-8hvNgsP5g",
            published_at="2026-05-14",
            view_count=100,
        )

        with self.repo.db.connect() as conn:
            row = conn.execute(
                "SELECT title, channel, channel_id FROM candidate_frontier WHERE video_id = ?",
                ("82Zi7ZrHeY8",),
            ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["title"], "I Tried Exotic Food On Facebook Marketplace!")
        self.assertEqual(row["channel"], "Nick Kratka")
        self.assertEqual(row["channel_id"], "UCRPNk3TA5cbyB-8hvNgsP5g")

    def test_startup_repair_demotes_legacy_display_metadata_placeholders(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo("ezmTq7I5Vf8", "Good title", "Real Channel", "chan1", 100, None, source_id, to_iso())
        )
        self.repo.store_inspection_result(
            "ezmTq7I5Vf8",
            audio_languages=["en", "es"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"]},
            title="Good title",
            channel="Real Channel",
            published_at="2026-05-14",
            view_count=100,
        )
        with self.repo.db.connect() as conn:
            conn.execute(
                """
                UPDATE videos
                SET title = video_id, channel = 'Real Channel', metadata_complete = 1
                WHERE video_id = 'ezmTq7I5Vf8'
                """
            )

        repaired = self.repo.repair_display_metadata_flags()

        with self.repo.db.connect() as conn:
            row = conn.execute(
                "SELECT metadata_complete FROM videos WHERE video_id = 'ezmTq7I5Vf8'"
            ).fetchone()
        self.assertEqual(repaired, 1)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["metadata_complete"], 0)

    def test_catalog_defensively_hides_stale_complete_flag_with_id_title(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo("HH2gKrl22Fw", "Good title", "Aquarium Info", "chan1", 100, None, source_id, to_iso())
        )
        self.repo.store_inspection_result(
            "HH2gKrl22Fw",
            audio_languages=["en-US", "es"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en-US"]},
            title="Good title",
            channel="Aquarium Info",
            published_at="2026-04-18",
            view_count=100,
        )
        with self.repo.db.connect() as conn:
            conn.execute(
                """
                UPDATE videos
                SET title = video_id, metadata_complete = 1
                WHERE video_id = 'HH2gKrl22Fw'
                """
            )

        catalog = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )

        self.assertEqual(catalog, [])

    def test_candidate_upsert_does_not_overwrite_repaired_metadata_with_placeholders(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(CandidateVideo("zRtGL0-5rg4", "Good", "MrBeast", "chan1", 100, None, source_id, to_iso()))
        self.repo.store_inspection_result(
            "zRtGL0-5rg4",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_kind="automatic",
            dub_evidence={"source": "yt_dlp", "original_audio_languages": ["en"], "auto_dubbed_languages": ["es-US"]},
            title="Last To Leave Grocery Store, Wins $250,000",
            channel="MrBeast",
            published_at="2026-04-20",
            view_count=100,
        )

        self.repo.upsert_candidate(
            CandidateVideo(
                "zRtGL0-5rg4",
                "zRtGL0-5rg4",
                "Last To Leave Grocery Store, Wins $250,000",
                "chan1",
                100,
                None,
                source_id,
                to_iso(),
            )
        )

        with self.repo.db.connect() as conn:
            row = conn.execute(
                "SELECT title, channel FROM videos WHERE video_id = ?",
                ("zRtGL0-5rg4",),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["title"], "Last To Leave Grocery Store, Wins $250,000")
        self.assertEqual(row["channel"], "MrBeast")

    def test_spanish_catalog_filter_splits_manual_and_automatic_dubs(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        rows = {
            "manual_es": (["en", "es-419"], "manual", [], ["en"]),
            "automatic_es": (["en", "es-419"], "automatic", ["es-419"], ["en"]),
            "manual_fr": (["en", "fr-FR"], "manual", [], ["en"]),
        }

        for video_id, (languages, dub_kind, auto_languages, original_languages) in rows.items():
            self.repo.upsert_candidate(CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso()))
            self.repo.store_inspection_result(
                video_id,
                audio_languages=languages,
                has_dubbing=True,
                dub_kind=dub_kind,
                dub_evidence={
                    "source": "inspection",
                    "auto_dubbed_languages": auto_languages,
                    "original_audio_languages": original_languages,
                },
                published_at="2026-04-20",
                view_count=100,
            )

        manual = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
        )
        automatic = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="automatic",
        )

        self.assertEqual({item["video_id"] for item in manual}, {"manual_es"})
        self.assertEqual({item["video_id"] for item in automatic}, {"automatic_es"})

    def test_spanish_catalog_hides_spanish_original_tracks(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        rows = {
            "spanish_original": (["en-US", "es-US", "pt-BR"], ["es-US"], "manual", []),
            "spanish_manual_dub": (["en-US", "es-US"], ["en-US"], "manual", []),
            "spanish_ai_dub": (["en-US", "es-US"], ["en-US"], "automatic", ["es-US"]),
        }

        for video_id, (languages, original_languages, dub_kind, auto_languages) in rows.items():
            self.repo.upsert_candidate(CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso()))
            self.repo.store_inspection_result(
                video_id,
                audio_languages=languages,
                has_dubbing=True,
                dub_kind=dub_kind,
                dub_evidence={
                    "source": "yt_dlp",
                    "languages": languages,
                    "original_audio_languages": original_languages,
                    "auto_dubbed_languages": auto_languages,
                },
                published_at="2026-04-20",
                view_count=100,
            )

        all_spanish = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        manual = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
        )
        automatic = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="automatic",
        )

        self.assertEqual({item["video_id"] for item in all_spanish}, {"spanish_manual_dub", "spanish_ai_dub"})
        self.assertEqual({item["video_id"] for item in manual}, {"spanish_manual_dub"})
        self.assertEqual({item["video_id"] for item in automatic}, {"spanish_ai_dub"})
        with self.repo.db.connect() as conn:
            original_flag = conn.execute(
                """
                SELECT is_original_audio
                FROM video_audio_tracks
                WHERE video_id = 'spanish_original' AND language_code = 'es-US'
                """
            ).fetchone()[0]
            translated_flag = conn.execute(
                """
                SELECT is_original_audio
                FROM video_audio_tracks
                WHERE video_id = 'spanish_manual_dub' AND language_code = 'es-US'
                """
            ).fetchone()[0]
        self.assertEqual(original_flag, 1)
        self.assertEqual(translated_flag, 0)

    def test_spanish_automatic_filter_uses_spanish_track_evidence_not_video_label(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        rows = [
            ("auto_es", ["en", "es", "fr"], "automatic", ["es"]),
            ("auto_fr_only", ["en", "es", "fr"], "automatic", ["fr"]),
        ]

        for video_id, languages, dub_kind, auto_languages in rows:
            self.repo.upsert_candidate(CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso()))
            self.repo.store_inspection_result(
                video_id,
                audio_languages=languages,
                has_dubbing=True,
                dub_kind=dub_kind,
                dub_evidence={
                    "source": "inspection",
                    "auto_dubbed_languages": auto_languages,
                    "original_audio_languages": ["en"],
                },
                published_at="2026-04-20",
                view_count=100,
            )

        automatic = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="automatic",
        )
        unconfirmed = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
        )

        self.assertEqual([item["video_id"] for item in automatic], ["auto_es"])
        self.assertEqual([item["video_id"] for item in unconfirmed], ["auto_fr_only"])

    def test_catalog_keeps_large_multiaudio_manual_rows_out_of_automatic_filter(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        manual_candidate = CandidateVideo("manual1", "Manual", "Chan", "chan1", 100, None, source_id, to_iso())
        large_multiaudio_candidate = CandidateVideo("large1", "Large", "Chan", "chan1", 100, None, source_id, to_iso())
        self.repo.upsert_candidate(manual_candidate)
        self.repo.upsert_candidate(large_multiaudio_candidate)
        self.repo.store_inspection_result(
            "manual1",
            audio_languages=["en-US", "es-US"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en-US"], "auto_dubbed_languages": []},
            published_at="2026-04-20",
            view_count=100,
        )
        self.repo.store_inspection_result(
            "large1",
            audio_languages=["ar", "bn", "de", "en", "es", "fr", "hi", "id", "it", "ja"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2026-04-20",
            view_count=100,
        )

        manual = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
        )
        automatic = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="automatic",
        )

        self.assertEqual({item["video_id"] for item in manual}, {"manual1", "large1"})
        self.assertEqual(automatic, [])

    def test_manual_filter_hides_old_ytdlp_manual_rows_until_reclassified(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo("oldytdlp001", "Old yt-dlp", "Chan", "chan1", 100, None, source_id, to_iso())
        )
        self.repo.store_inspection_result(
            "oldytdlp001",
            audio_languages=["en-US", "es-US"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={
                "source": "yt_dlp",
                "original_audio_languages": ["en-US"],
                "auto_dubbed_languages": [],
            },
            classifier_version=CURRENT_DUB_CLASSIFIER_VERSION - 1,
            published_at="2026-04-20",
            view_count=100,
        )

        all_dubs = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        manual = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
        )

        self.assertEqual([item["video_id"] for item in all_dubs], ["oldytdlp001"])
        self.assertEqual(manual, [])

    def test_store_inspection_ignores_descriptive_audio_for_dubbing(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(CandidateVideo("desc1", "Desc", "Chan", "chan1", 100, None, source_id, to_iso()))

        self.repo.store_inspection_result(
            "desc1",
            audio_languages=["en", "en-desc"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=100,
        )

        dubbed = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        all_items = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=False,
        )
        self.assertEqual(dubbed, [])
        self.assertEqual(all_items[0]["audio_languages"], ["en"])
        self.assertEqual(all_items[0]["dub_kind"], "none")

    def test_delete_sources_can_remove_only_unique_source_videos(self) -> None:
        source_a = self.repo.create_source(SourceInput("search", "A", "demo a", 5))
        source_b = self.repo.create_source(SourceInput("search", "B", "demo b", 5))
        source_c = self.repo.create_source(SourceInput("search", "C", "demo c", 5))

        self.repo.upsert_candidate(CandidateVideo("unique-a", "Unique", "Chan", "chan1", 100, None, source_a, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("shared", "Shared", "Chan", "chan1", 100, None, source_a, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("shared", "Shared", "Chan", "chan1", 100, None, source_b, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("other", "Other", "Chan", "chan1", 100, None, source_c, to_iso()))

        self.repo.delete_sources([source_a], delete_videos=True)

        with self.repo.db.connect() as conn:
            video_ids = {row["video_id"] for row in conn.execute("SELECT video_id FROM videos").fetchall()}
            shared_sources = [
                row["source_id"]
                for row in conn.execute(
                    "SELECT source_id FROM video_sources WHERE video_id = ?",
                    ("shared",),
                ).fetchall()
            ]

        self.assertNotIn("unique-a", video_ids)
        self.assertIn("shared", video_ids)
        self.assertIn("other", video_ids)
        self.assertEqual(shared_sources, [source_b])

    def test_sources_report_full_state_and_increase_full_limits(self) -> None:
        full_a = self.repo.create_source(SourceInput("search", "Full A", "demo a", 2))
        full_b = self.repo.create_source(SourceInput("search", "Full B", "demo b", 1))
        partial = self.repo.create_source(SourceInput("search", "Partial", "demo c", 3))

        self.repo.upsert_candidate(CandidateVideo("a1", "A1", "Chan", "chan1", 100, None, full_a, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("a2", "A2", "Chan", "chan1", 100, None, full_a, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("b1", "B1", "Chan", "chan1", 100, None, full_b, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("c1", "C1", "Chan", "chan1", 100, None, partial, to_iso()))

        sources_by_id = {int(source["id"]): source for source in self.repo.list_sources()}
        self.assertEqual(sources_by_id[full_a]["video_count"], 2)
        self.assertEqual(sources_by_id[full_b]["is_full"], 1)
        self.assertEqual(sources_by_id[partial]["is_full"], 0)

        changed = self.repo.increase_full_source_limits(500)

        self.assertEqual(changed, 2)
        sources_by_id = {int(source["id"]): source for source in self.repo.list_sources()}
        self.assertEqual(sources_by_id[full_a]["max_candidates_per_run"], 502)
        self.assertEqual(sources_by_id[full_b]["max_candidates_per_run"], 501)
        self.assertEqual(sources_by_id[partial]["max_candidates_per_run"], 3)
        self.assertEqual(sources_by_id[full_a]["is_full"], 0)

    def test_catalog_page_and_count_use_pagination(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        for index in range(5):
            video_id = f"page{index}"
            self.repo.upsert_candidate(
                CandidateVideo(video_id, video_id, "Chan", "chan1", 100, None, source_id, to_iso())
            )
            self.repo.store_inspection_result(
                video_id,
                audio_languages=["en", "es-US"],
                has_dubbing=True,
                dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
                published_at=f"2026-04-{20 + index:02d}",
                view_count=index,
            )

        self.assertEqual(
            self.repo.count_catalog(
                lang=SPANISH_LANGUAGE_FILTER,
                source_id=None,
                channel=None,
                query=None,
                only_dubbed=True,
                dub_kind="manual",
            ),
            5,
        )
        page_one = self.repo.list_catalog_page(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
            sort_by="recent",
            page_size=2,
        )
        page_two = self.repo.list_catalog_page(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
            sort_by="recent",
            page_size=2,
            cursor=page_one["next_cursor"],
        )

        self.assertEqual([row["video_id"] for row in page_one["items"]], ["page4", "page3"])
        self.assertEqual([row["video_id"] for row in page_two["items"]], ["page2", "page1"])

    def test_scheduler_jobs_claim_finish_and_recover(self) -> None:
        job_id = self.repo.enqueue_job(
            job_type="metadata_refresh",
            payload={"video_id": "abc123"},
            idempotency_key="metadata:abc123",
            priority=5,
        )
        claimed = self.repo.claim_jobs(owner="test", limit=1, lease_seconds=30)
        self.assertEqual([job["id"] for job in claimed], [job_id])
        self.assertEqual(claimed[0]["payload"], {"video_id": "abc123"})
        self.repo.finish_job(job_id)
        self.assertEqual(self.repo.claim_jobs(owner="test", limit=1), [])

        stale_id = self.repo.enqueue_job(
            job_type="inspect_light",
            payload={"video_id": "stale"},
            idempotency_key="inspect:stale",
            priority=5,
        )
        self.repo.claim_jobs(owner="test", limit=1, lease_seconds=30)
        with self.repo.db.connect() as conn:
            conn.execute(
                "UPDATE scheduler_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
                (stale_id,),
            )
        self.repo.recover_scheduler_jobs()
        recovered = self.repo.claim_jobs(owner="second", limit=1, lease_seconds=30)
        self.assertEqual([job["id"] for job in recovered], [stale_id])

    def test_discovery_seed_deduplicates_and_migrates_sources(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "Anime", "anime doblado", 100))

        seed_id = self.repo.create_discovery_seed(
            seed_kind="user_search",
            source_type="search",
            label="Anime",
            value="anime doblado",
            priority=20,
        )
        duplicate_id = self.repo.create_discovery_seed(
            seed_kind="user_search",
            source_type="search",
            label="Anime copy",
            value="anime doblado",
            priority=10,
        )

        self.assertEqual(seed_id, duplicate_id)
        seeds = self.repo.list_discovery_seeds()
        self.assertEqual(len(seeds), 1)
        self.assertEqual(seeds[0]["priority"], 10)
        self.assertEqual(seeds[0]["source_type"], "search")
        self.assertNotEqual(source_id, 0)

    def test_candidate_frontier_claims_and_marks_verified_or_rejected(self) -> None:
        seed_id = self.repo.create_discovery_seed(
            seed_kind="related_video",
            source_type="video",
            label="Seed",
            value="seed123",
            priority=50,
        )

        self.repo.enqueue_candidate(
            {
                "video_id": "cand1",
                "title": "Candidate",
                "channel": "Channel",
                "channel_id": "chan1",
                "duration_seconds": 120,
                "thumbnail_url": "thumb.jpg",
                "published_at": "2026-04-20",
                "view_count": 50,
            },
            source_seed_id=seed_id,
            discovered_from_video_id="seed123",
            priority=15,
            score=0.75,
        )
        self.repo.enqueue_candidate(
            {"video_id": "cand1", "title": "Candidate updated"},
            source_seed_id=seed_id,
            discovered_from_video_id="seed123",
            priority=5,
            score=0.9,
        )

        claimed = self.repo.claim_frontier_candidates(limit=1)

        self.assertEqual([item["video_id"] for item in claimed], ["cand1"])
        self.assertEqual(claimed[0]["title"], "Candidate updated")
        self.assertEqual(claimed[0]["priority"], 5)
        self.repo.mark_candidate_verified("cand1")
        self.assertEqual(self.repo.claim_frontier_candidates(limit=1), [])

        self.repo.enqueue_candidate({"video_id": "cand2", "title": "Plain"}, priority=10)
        self.repo.mark_candidate_rejected("cand2", "no dubbing")
        states = {row["video_id"]: row["state"] for row in self.repo.list_frontier_candidates()}
        self.assertEqual(states["cand1"], "verified")
        self.assertEqual(states["cand2"], "rejected")

    def test_frontier_claim_prioritizes_less_saturated_channels(self) -> None:
        seed_id = self.repo.create_discovery_seed(
            seed_kind="related_video",
            source_type="video",
            label="Seed",
            value="seed123",
            priority=50,
        )
        for index in range(3):
            self.repo.enqueue_candidate(
                {
                    "video_id": f"crowded{index}",
                    "title": f"Crowded {index}",
                    "channel": "Crowded Channel",
                    "channel_id": "crowded",
                },
                source_seed_id=seed_id,
                priority=20,
                score=1.0,
            )
        self.repo.enqueue_candidate(
            {
                "video_id": "rare1",
                "title": "Rare",
                "channel": "Rare Channel",
                "channel_id": "rare",
            },
            source_seed_id=seed_id,
            priority=20,
            score=1.0,
        )

        claimed = self.repo.claim_frontier_candidates(limit=1)

        self.assertEqual([item["video_id"] for item in claimed], ["rare1"])

    def test_frontier_claim_treats_missing_channel_as_unique(self) -> None:
        for index in range(2):
            self.repo.enqueue_candidate(
                {
                    "video_id": f"crowded{index}",
                    "title": f"Crowded {index}",
                    "channel": "Crowded Channel",
                    "channel_id": "crowded",
                },
                priority=20,
                score=1.0,
            )
        self.repo.enqueue_candidate({"video_id": "unknown1", "title": "Unknown 1"}, priority=20, score=1.0)
        self.repo.enqueue_candidate({"video_id": "unknown2", "title": "Unknown 2"}, priority=20, score=1.0)

        claimed = self.repo.claim_frontier_candidates(limit=2)

        self.assertEqual({item["video_id"] for item in claimed}, {"unknown1", "unknown2"})

    def test_discovery_seed_claim_prioritizes_less_saturated_video_channels(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        for index in range(3):
            video_id = f"crowded_seed_{index}"
            self.repo.upsert_candidate(
                CandidateVideo(video_id, f"Crowded {index}", "Crowded Channel", "crowded", 100, None, source_id, to_iso())
            )
            self.repo.create_discovery_seed(
                seed_kind="related_video",
                source_type="video",
                label=f"Crowded {index}",
                value=video_id,
                priority=80,
            )
        self.repo.upsert_candidate(
            CandidateVideo("rare_seed", "Rare", "Rare Channel", "rare", 100, None, source_id, to_iso())
        )
        self.repo.create_discovery_seed(
            seed_kind="related_video",
            source_type="video",
            label="Rare",
            value="rare_seed",
            priority=80,
        )

        claimed = self.repo.claim_discovery_seeds(limit=1, randomize=False)

        self.assertEqual([item["value"] for item in claimed], ["rare_seed"])

    def test_discovery_seed_claim_keeps_user_seeds_ahead_of_video_entropy(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        self.repo.upsert_candidate(
            CandidateVideo("video_seed", "Video", "Video Channel", "video-channel", 100, None, source_id, to_iso())
        )
        self.repo.create_discovery_seed(
            seed_kind="related_video",
            source_type="video",
            label="Video",
            value="video_seed",
            priority=50,
        )
        self.repo.create_discovery_seed(
            seed_kind="user_search",
            source_type="search",
            label="User interest",
            value="user interest",
            priority=50,
        )

        claimed = self.repo.claim_discovery_seeds(limit=1, randomize=False)

        self.assertEqual([item["seed_kind"] for item in claimed], ["user_search"])

    def test_import_content_pool_creates_system_search_seeds_idempotently(self) -> None:
        pool_path = Path(self.temp_dir.name) / "content_pool.json"
        pool_path.write_text(
            json.dumps(
                {
                    "version": "test-v1",
                    "theme_queries": [
                        {"query": "streamer controversy explained", "priority": 45},
                        {"query": "internet mysteries explained", "priority": 50},
                    ],
                }
            ),
            encoding="utf-8",
        )

        first = self.repo.import_content_pool(pool_path, version="test-v1")
        second = self.repo.import_content_pool(pool_path, version="test-v1")

        self.assertEqual(first["imported"], 2)
        self.assertEqual(second["imported"], 0)
        seeds = self.repo.list_discovery_seeds()
        self.assertEqual(len(seeds), 2)
        self.assertEqual({seed["seed_kind"] for seed in seeds}, {"system_search"})
        self.assertEqual({seed["source_type"] for seed in seeds}, {"search"})

    def test_import_content_pool_can_create_system_channel_seeds(self) -> None:
        pool_path = Path(self.temp_dir.name) / "content_pool_channels.json"
        pool_path.write_text(
            json.dumps(
                {
                    "version": "test-v3",
                    "theme_queries": [
                        {"query": "the problem with YouTube", "priority": 50},
                        {
                            "type": "channel",
                            "label": "Evan Carmichael",
                            "value": "UCKmkpoEqg1sOMGEiIysP8Tw",
                            "priority": 35,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = self.repo.import_content_pool(pool_path, version="test-v3")

        seeds = {seed["value"]: seed for seed in self.repo.list_discovery_seeds()}
        self.assertEqual(result["imported"], 2)
        self.assertEqual(seeds["the problem with YouTube"]["seed_kind"], "system_search")
        self.assertEqual(seeds["the problem with YouTube"]["source_type"], "search")
        self.assertEqual(seeds["UCKmkpoEqg1sOMGEiIysP8Tw"]["seed_kind"], "system_channel")
        self.assertEqual(seeds["UCKmkpoEqg1sOMGEiIysP8Tw"]["source_type"], "channel")

    def test_import_content_pool_can_replace_packaged_system_search_seeds(self) -> None:
        self.repo.create_discovery_seed(
            seed_kind="system_search",
            source_type="search",
            label="Old packaged query",
            value="streamer controversy explained",
            priority=50,
        )
        self.repo.create_discovery_seed(
            seed_kind="user_search",
            source_type="search",
            label="Manual query",
            value="mrbeast",
            priority=50,
        )
        pool_path = Path(self.temp_dir.name) / "content_pool_v2.json"
        pool_path.write_text(
            json.dumps(
                {
                    "version": "test-v2",
                    "replace_existing_system_search": True,
                    "theme_queries": [
                        {"query": "the problem with YouTube", "priority": 50},
                        {"query": "influencer got exposed", "priority": 50},
                    ],
                }
            ),
            encoding="utf-8",
        )

        self.repo.import_content_pool(pool_path, version="test-v2")

        seeds = {seed["value"]: seed for seed in self.repo.list_discovery_seeds()}
        self.assertEqual(seeds["streamer controversy explained"]["enabled"], 0)
        self.assertEqual(seeds["mrbeast"]["enabled"], 1)
        self.assertEqual(seeds["the problem with YouTube"]["enabled"], 1)
        self.assertEqual(seeds["influencer got exposed"]["enabled"], 1)

    def test_recent_complete_videos_are_rechecked_for_late_manual_dubs(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        recent_day = utc_now().date().isoformat()
        old_check = to_iso(utc_now() - timedelta(hours=13))
        fresh_check = to_iso(utc_now() - timedelta(hours=1))

        for video_id, checked_at in (("recent_recheck", old_check), ("fresh_recheck", fresh_check)):
            self.repo.upsert_candidate(
                CandidateVideo(video_id, f"Title {video_id}", "Chan", "chan1", 100, None, source_id, to_iso())
            )
            self.repo.store_inspection_result(
                video_id,
                audio_languages=["en-US", "es-US"],
                has_dubbing=True,
                dub_kind="automatic",
                dub_evidence={
                    "source": "inspection",
                    "auto_dubbed_languages": ["es-US"],
                    "original_audio_languages": ["en-US"],
                },
                published_at=recent_day,
                view_count=100,
            )
            with self.repo.db.connect() as conn:
                conn.execute(
                    "UPDATE videos SET last_checked_at = ?, metadata_sort_at = ? WHERE video_id = ?",
                    (checked_at, checked_at, video_id),
                )

        missing = self.repo.list_video_ids_missing_metadata(
            limit=10,
            recent_recheck_days=21,
            recent_recheck_hours=12,
        )

        self.assertIn("recent_recheck", missing)
        self.assertNotIn("fresh_recheck", missing)

    def test_mixed_discovery_seed_claim_uses_seven_content_and_three_free_slots(self) -> None:
        for index in range(8):
            self.repo.create_discovery_seed(
                seed_kind="system_search",
                source_type="search",
                label=f"Content {index}",
                value=f"content {index}",
                priority=50,
            )
        for index in range(5):
            self.repo.create_discovery_seed(
                seed_kind="related_video",
                source_type="video",
                label=f"Free {index}",
                value=f"free{index}",
                priority=80,
            )

        claimed = self.repo.claim_discovery_seeds_mixed(limit=10, randomize=False)

        kinds = [seed["seed_kind"] for seed in claimed]
        self.assertEqual(len(claimed), 10)
        self.assertEqual(kinds.count("system_search"), 7)
        self.assertEqual(kinds.count("related_video"), 3)

    def test_mixed_discovery_seed_claim_treats_user_inputs_as_content_pool(self) -> None:
        self.repo.create_discovery_seed(
            seed_kind="user_search",
            source_type="search",
            label="User search",
            value="user search",
            priority=10,
        )
        self.repo.create_discovery_seed(
            seed_kind="user_channel",
            source_type="channel",
            label="User channel",
            value="https://www.youtube.com/@demo/videos",
            priority=10,
        )
        for index in range(3):
            self.repo.create_discovery_seed(
                seed_kind="related_video",
                source_type="video",
                label=f"Free {index}",
                value=f"free-user-{index}",
                priority=80,
            )

        claimed = self.repo.claim_discovery_seeds_mixed(limit=5, randomize=False)

        claimed_kinds = {seed["seed_kind"] for seed in claimed}
        self.assertIn("user_search", claimed_kinds)
        self.assertIn("user_channel", claimed_kinds)

    def test_mixed_discovery_seed_claim_falls_back_to_available_pool(self) -> None:
        for index in range(4):
            self.repo.create_discovery_seed(
                seed_kind="related_video",
                source_type="video",
                label=f"Free {index}",
                value=f"only-free-{index}",
                priority=80,
            )

        only_free = self.repo.claim_discovery_seeds_mixed(limit=3, randomize=False)
        self.assertEqual(len(only_free), 3)
        self.assertEqual({seed["seed_kind"] for seed in only_free}, {"related_video"})

        second_repo = Repository(Database(Path(self.temp_dir.name) / "second.db"))
        second_repo.db.initialize()
        for index in range(4):
            second_repo.create_discovery_seed(
                seed_kind="system_search",
                source_type="search",
                label=f"Content {index}",
                value=f"only content {index}",
                priority=50,
            )

        only_content = second_repo.claim_discovery_seeds_mixed(limit=3, randomize=False)
        self.assertEqual(len(only_content), 3)
        self.assertEqual({seed["seed_kind"] for seed in only_content}, {"system_search"})

    def test_counts_video_discovery_seeds_for_channel(self) -> None:
        source_id = self.repo.create_source(SourceInput("search", "A", "demo", 5))
        for index in range(2):
            video_id = f"seed_{index}"
            self.repo.upsert_candidate(
                CandidateVideo(video_id, f"Seed {index}", "Seed Channel", "seed-channel", 100, None, source_id, to_iso())
            )
            self.repo.create_discovery_seed(
                seed_kind="related_video",
                source_type="video",
                label=f"Seed {index}",
                value=video_id,
                priority=80,
            )

        self.assertEqual(self.repo.count_video_discovery_seeds_for_channel("seed-channel", "Seed Channel"), 2)
        self.assertEqual(self.repo.count_video_discovery_seeds_for_channel("missing-channel", "Missing"), 0)

    def test_merge_starter_pack_deduplicates_videos_and_records_version(self) -> None:
        starter_path = Path(self.temp_dir.name) / "starter.db"
        starter_repo = Repository(Database(starter_path))
        starter_repo.db.initialize()
        source_id = starter_repo.create_source(SourceInput("search", "Starter", "starter", 10))
        starter_repo.upsert_candidate(
            CandidateVideo("starter1", "Starter video", "Starter Channel", "chan1", 90, None, source_id, to_iso())
        )
        starter_repo.store_inspection_result(
            "starter1",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2026-04-20",
            view_count=123,
        )

        result = self.repo.merge_starter_pack(starter_path, version="test-v1")
        result_again = self.repo.merge_starter_pack(starter_path, version="test-v1")

        self.assertEqual(result["inserted_videos"], 1)
        self.assertEqual(result_again["skipped"], True)
        catalog = self.repo.list_catalog_page(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            page_size=10,
        )
        self.assertEqual([item["video_id"] for item in catalog["items"]], ["starter1"])

    def test_merge_starter_pack_repairs_existing_spanish_ai_track_flags(self) -> None:
        starter_path = Path(self.temp_dir.name) / "legacy_starter.db"
        starter_repo = Repository(Database(starter_path))
        starter_repo.db.initialize()
        source_id = starter_repo.create_source(SourceInput("search", "Starter", "starter", 10))
        starter_repo.upsert_candidate(
            CandidateVideo("legacy_auto", "Legacy starter", "Starter Channel", "chan1", 90, None, source_id, to_iso())
        )
        starter_repo.store_inspection_result(
            "legacy_auto",
            audio_languages=["en", "es"],
            has_dubbing=True,
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2026-04-20",
            view_count=100,
        )
        with starter_repo.db.connect() as conn:
            conn.execute(
                """
                UPDATE videos
                SET dub_kind = 'automatic',
                    dub_confidence = 'high',
                    dub_evidence_json = '{"source":"inspection","languages":["en","es"],"original_audio_languages":["en"]}'
                WHERE video_id = 'legacy_auto'
                """
            )
            conn.execute("UPDATE video_audio_tracks SET is_auto_dubbed = 1 WHERE video_id = 'legacy_auto'")

        local_source_id = self.repo.create_source(SourceInput("search", "Local", "local", 10))
        self.repo.upsert_candidate(
            CandidateVideo("legacy_auto", "Existing local", "Starter Channel", "chan1", 90, None, local_source_id, to_iso())
        )
        self.repo.store_inspection_result(
            "legacy_auto",
            audio_languages=["en", "es"],
            has_dubbing=True,
            dub_kind="manual",
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2026-04-20",
            view_count=100,
        )

        self.repo.merge_starter_pack(starter_path, version="legacy-auto")

        automatic = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="automatic",
        )
        unconfirmed = self.repo.list_catalog(
            lang=SPANISH_LANGUAGE_FILTER,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            dub_kind="manual",
        )

        self.assertEqual([item["video_id"] for item in automatic], ["legacy_auto"])
        self.assertEqual(unconfirmed, [])


if __name__ == "__main__":
    unittest.main()
