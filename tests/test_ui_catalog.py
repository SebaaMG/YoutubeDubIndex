from __future__ import annotations

import os
import time
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app import ui as ui_module
from app.config import Settings
from app.db import Database
from app.desktop_services import AppController, DesktopServices
from app.repository import SPANISH_LANGUAGE_FILTER, CandidateVideo, Repository, SourceInput, to_iso
from app.ui import APP_STYLE, THUMBNAIL_RENDER_SCALE, YOUTUBE_FIRST_YEAR, MainWindow, ThumbnailService, combo_year_value
from app.youtube import StartupDiagnostics, YouTubeService


def wait_for_catalog_idle(window: MainWindow, app: QApplication, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        page_threads = getattr(window, "_catalog_page_threads", [])
        filter_threads = getattr(window, "_catalog_filter_threads", [])
        if (
            not getattr(window, "_catalog_loading_page", False)
            and not getattr(window, "_catalog_filters_loading", False)
            and not any(thread.is_alive() for thread in page_threads)
            and not any(thread.is_alive() for thread in filter_threads)
        ):
            app.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("catalog did not become idle")


def wait_for_catalog_count_idle(window: MainWindow, app: QApplication, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        count_threads = getattr(window, "_catalog_count_threads", [])
        if (
            not getattr(window, "_catalog_count_pending", False)
            and not any(thread.is_alive() for thread in count_threads)
        ):
            app.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("catalog count did not become idle")


def wait_for_summary_idle(window: MainWindow, app: QApplication, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        summary_threads = getattr(window, "_summary_refresh_threads", [])
        if (
            not getattr(window, "_summary_refresh_loading", False)
            and not any(thread.is_alive() for thread in summary_threads)
        ):
            app.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("summary refresh did not become idle")


class FakeRunner:
    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo
        self.calls: list[dict[str, object]] = []
        self._active_run_id: int | None = None

    def active_run_id(self) -> int | None:
        return self._active_run_id

    def start_run(self, *args: object, **kwargs: object) -> int:
        self.calls.append({"args": args, "kwargs": kwargs})
        scope = str(kwargs.get("scope", "all"))
        if self.repo is not None:
            run_id = self.repo.create_run(scope)
            self.repo.mark_run_running(run_id)
        else:
            run_id = len(self.calls)
        self._active_run_id = run_id
        return run_id


class FakeDiscoveryWorker:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.immediate_calls: list[dict[str, object]] = []

    def run_manual_feed_batch(
        self,
        *,
        candidate_limit: int = 50,
        max_seed_discoveries: int | None = None,
    ) -> dict[str, int]:
        self.calls.append(
            {
                "candidate_limit": candidate_limit,
                "max_seed_discoveries": max_seed_discoveries,
            }
        )
        return {
            "seeds": 1,
            "related_candidates": 60,
            "inspected": candidate_limit,
            "verified": 12,
            "rejected": candidate_limit - 12,
            "failed": 0,
        }

    def enqueue_immediate_seed_candidates(self, seed_id: int, *, candidate_limit: int = 150) -> dict[str, int]:
        self.immediate_calls.append({"seed_id": seed_id, "candidate_limit": candidate_limit})
        return {
            "seeds": 1,
            "related_candidates": candidate_limit,
            "inspected": 0,
            "verified": 0,
            "rejected": 0,
            "failed": 0,
        }


class CatalogUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(APP_STYLE)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings(project_root=Path(self.temp_dir.name))
        db = Database(settings.db_path)
        db.initialize()
        repo = Repository(db)
        self.repo = repo

        source_id = repo.create_source(SourceInput("search", "mark rober", "mark rober", 10, True))
        self.source_id = source_id
        repo.upsert_candidate(
            CandidateVideo(
                video_id="abc123",
                title="Lava vs Lasers",
                channel="Mark Rober",
                channel_id="chan1",
                duration_seconds=1240,
                thumbnail_url="https://i.ytimg.com/vi/abc123/hqdefault.jpg",
                source_id=source_id,
                discovered_at=to_iso(),
            )
        )
        repo.store_inspection_result(
            "abc123",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2026-04-22",
            view_count=12345,
        )

        self.runner = FakeRunner(repo)
        services = DesktopServices(
            settings=settings,
            db=db,
            repo=repo,
            youtube=YouTubeService(settings),
            runner=self.runner,
            diagnostics=StartupDiagnostics(node_ok=True, ytdlp_ok=True, messages=[]),
        )
        self.services = services
        self.controller = AppController(services)
        self.window = MainWindow(self.controller, services)

    def tearDown(self) -> None:
        self.window.close()
        self.temp_dir.cleanup()

    def test_app_opens_on_discover_catalog(self) -> None:
        self.assertEqual(self.window.pages.currentIndex(), self.window.page_index["catalog"])

    def test_dashboard_keeps_provisional_brand_and_metric_cards_out_of_ui(self) -> None:
        label_texts = [label.text() for label in self.window.findChildren(QLabel)]

        self.assertNotIn("DubIndex", label_texts)
        self.assertEqual(self.window.windowTitle().strip(), "")
        self.assertEqual(self.window.statusBar().currentMessage(), "")
        self.assertEqual(self.window._nav_buttons["catalog"].text(), "Descubrir")
        self.assertNotIn("sources", self.window._nav_buttons)
        self.assertFalse(hasattr(self.window, "dubbed_videos_card"))
        self.assertFalse(hasattr(self.window, "total_videos_card"))
        self.assertFalse(hasattr(self.window, "sources_count_card"))

    def test_catalog_shows_essential_controls_and_collapsed_filters(self) -> None:
        self.window.resize(1600, 1000)
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)

        self.assertTrue(self.window.catalog_controls_shell.isVisible())
        self.assertFalse(self.window.catalog_filters_panel.isVisible())
        self.assertEqual(self.window.catalog_filters_toggle.text(), "Mas filtros")
        self.assertEqual(self.window.catalog_model.rowCount(), 1)
        self.assertEqual(self.window.catalog_results_count.text(), "1 encontrados")
        self.assertTrue(self.window.catalog_visibility.currentData())
        self.assertEqual(self.window.catalog_dub_kind.currentData(), "")
        self.assertEqual(self.window.catalog_dub_kind.itemText(0), "Todos los dubs")
        self.assertLess(self.window.catalog_dub_kind.findText("Dub real"), 0)
        self.assertLess(self.window.catalog_dub_kind.findText("Origen no confirmado"), 0)
        self.assertEqual(
            self.window.catalog_dub_kind.itemText(self.window.catalog_dub_kind.findData("automatic")),
            "Doblaje automático",
        )
        self.assertEqual(
            self.window.catalog_dub_kind.itemText(self.window.catalog_dub_kind.findData("manual")),
            "Doblaje manual",
        )
        self.assertLess(self.window.catalog_dub_kind.findText("IA"), 0)
        self.assertLess(self.window.catalog_dub_kind.findText("No IA"), 0)
        self.assertEqual(self.window.catalog_sort.currentData(), "recent")
        self.assertGreaterEqual(self.window.catalog_sort.findData("random"), 0)
        self.assertFalse(self.window.catalog_empty_stack.isVisible())

    def test_catalog_filter_panel_hides_source_search_section(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()

        self.window.toggle_catalog_filters()

        self.assertFalse(self.window.catalog_filters_panel.isHidden())
        self.assertFalse(self.window.catalog_source.isVisible())
        visible_filter_labels = [
            label.text()
            for label in self.window.catalog_filters_panel.findChildren(QLabel)
            if label.isVisibleTo(self.window.catalog_filters_panel)
        ]
        self.assertNotIn("Búsqueda", visible_filter_labels)

    def test_catalog_refresh_does_not_block_ui_while_page_query_runs(self) -> None:
        original_list_page = self.controller.list_catalog_page

        def slow_list_page(*args: object, **kwargs: object) -> dict[str, object]:
            time.sleep(0.2)
            return original_list_page(*args, **kwargs)

        self.controller.list_catalog_page = slow_list_page  # type: ignore[method-assign]
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()

        started = time.perf_counter()
        self.window.refresh_catalog()
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.08)
        self.assertTrue(self.window._catalog_loading_page)
        self.assertEqual(self.window.catalog_model.rowCount(), 0)

        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual(self.window.catalog_model.rowCount(), 1)

    def test_summary_refresh_does_not_block_ui_while_stats_query_runs(self) -> None:
        original_dashboard_stats = self.controller.dashboard_stats

        def slow_dashboard_stats(*args: object, **kwargs: object) -> dict[str, object]:
            time.sleep(0.2)
            return original_dashboard_stats(*args, **kwargs)

        self.controller.dashboard_stats = slow_dashboard_stats  # type: ignore[method-assign]
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()

        started = time.perf_counter()
        self.window.refresh_all()
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.08)
        self.assertTrue(self.window._summary_refresh_loading)

        wait_for_summary_idle(self.window, self.app)
        self.assertGreaterEqual(int(self.window._latest_stats.get("total_videos") or 0), 1)

    def test_startup_backfill_does_not_block_ui_while_metadata_query_runs(self) -> None:
        def slow_missing_metadata_count(*args: object, **kwargs: object) -> int:
            time.sleep(0.2)
            return 1

        def slow_start_backfill(*args: object, **kwargs: object) -> None:
            time.sleep(0.2)
            return None

        self.controller.count_videos_missing_metadata = slow_missing_metadata_count  # type: ignore[method-assign]
        self.controller.start_metadata_backfill = slow_start_backfill  # type: ignore[method-assign]

        started = time.perf_counter()
        self.window.start_metadata_backfill_if_needed()
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.08)

    def test_thumbnail_finish_schedules_decode_off_ui_thread(self) -> None:
        class FakeExecutor:
            def __init__(self) -> None:
                self.calls: list[tuple[object, tuple[object, ...]]] = []
                self.shutdown_kwargs: dict[str, object] | None = None

            def submit(self, fn: object, *args: object) -> None:
                self.calls.append((fn, args))

            def shutdown(self, **kwargs: object) -> None:
                self.shutdown_kwargs = dict(kwargs)

        class FakeReply:
            def __init__(self, data: bytes) -> None:
                self.data = data
                self.deleted = False

            def error(self) -> QNetworkReply.NetworkError:
                return QNetworkReply.NetworkError.NoError

            def readAll(self) -> bytes:
                return self.data

            def deleteLater(self) -> None:
                self.deleted = True

        owner = QWidget()
        service = ThumbnailService(owner, Path(self.temp_dir.name) / "thumbs")
        fake_executor = FakeExecutor()
        service._decode_pool = fake_executor  # type: ignore[assignment]
        key = ("https://example.test/thumb.jpg", 96, 54)
        callbacks: list[QSize] = []
        service._inflight[key] = [lambda pixmap: callbacks.append(pixmap.size())]

        reply = FakeReply(b"fake-image-bytes")
        started = time.perf_counter()
        service._finish(reply, key)  # type: ignore[arg-type]
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.05)
        self.assertTrue(reply.deleted)
        self.assertEqual(len(fake_executor.calls), 1)
        self.assertEqual(fake_executor.calls[0][1], (key, b"fake-image-bytes"))
        self.assertEqual(callbacks, [])
        self.assertIn(key, service._inflight)
        service.shutdown()
        self.assertEqual(fake_executor.shutdown_kwargs, {"wait": False, "cancel_futures": True})

    def test_thumbnail_render_scale_keeps_cards_clearer_than_half_resolution(self) -> None:
        self.assertEqual(THUMBNAIL_RENDER_SCALE, 0.75)

    def test_catalog_header_and_filter_bar_are_compact(self) -> None:
        self.window.resize(1600, 1000)
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()

        self.assertIn("font-size: 24px", self.window.catalog_intro_title.styleSheet())
        self.assertIn("font-size: 14px", self.window.catalog_intro_hint.styleSheet())
        self.assertEqual(self.window.catalog_query.maximumHeight(), 36)
        self.assertEqual(self.window.catalog_lang.maximumHeight(), 36)
        self.assertEqual(self.window.catalog_sort.maximumHeight(), 36)
        self.assertEqual(self.window.catalog_filters_toggle.maximumHeight(), 36)

    def test_catalog_grid_keeps_five_cards_per_row_at_scaled_desktop_width(self) -> None:
        for index in range(1, 8):
            video_id = f"scaled-{index}"
            self.repo.upsert_candidate(
                CandidateVideo(
                    video_id=video_id,
                    title=f"Scaled desktop video {index}",
                    channel="Mark Rober",
                    channel_id="chan1",
                    duration_seconds=120 + index,
                    thumbnail_url="",
                    source_id=self.source_id,
                    discovered_at=to_iso(),
                )
            )
            self.repo.store_inspection_result(
                video_id,
                audio_languages=["en", "es-US"],
                has_dubbing=True,
                dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
                published_at=f"2026-04-{10 + index:02d}",
                view_count=1000 + index,
            )

        self.window.resize(1280, 900)
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)

        first_row_y = {
            self.window.catalog_view.visualRect(self.window.catalog_model.index(row, 0)).y()
            for row in range(5)
        }
        sixth_y = self.window.catalog_view.visualRect(self.window.catalog_model.index(5, 0)).y()

        self.assertEqual(len(first_row_y), 1)
        self.assertGreater(sixth_y, next(iter(first_row_y)))

    def test_catalog_hides_card_until_upload_date_is_available(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        with self.repo.db.connect() as conn:
            conn.execute("UPDATE videos SET published_at = NULL WHERE video_id = 'abc123'")
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual(self.window.catalog_model.rowCount(), 0)

        self.repo.store_inspection_result(
            "abc123",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2026-04-22",
            view_count=12345,
        )
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)

        self.assertEqual(self.window.catalog_model.rowCount(), 1)
        self.assertEqual(self.window.catalog_model.item_at(0)["published_at"], "2026-04-22")

    def test_more_filters_toggle_reveals_secondary_filters(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog()

        self.window.toggle_catalog_filters()

        self.assertFalse(self.window.catalog_filters_panel.isHidden())
        self.assertEqual(self.window.catalog_filters_toggle.text(), "Ocultar filtros")

    def test_catalog_defaults_language_to_spanish_group(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog_filters()

        spanish_index = self.window.catalog_lang.findData(SPANISH_LANGUAGE_FILTER)
        self.assertGreaterEqual(spanish_index, 0)
        self.assertEqual(self.window.catalog_lang.itemText(spanish_index), "Español")
        self.assertEqual(self.window.catalog_lang.findData("es-US"), -1)
        self.assertEqual(self.window.catalog_lang.currentData(), SPANISH_LANGUAGE_FILTER)

    def test_catalog_dub_kind_changes_clear_stale_rows_without_clear_filters(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog_filters()
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)

        self.window.catalog_dub_kind.setCurrentIndex(self.window.catalog_dub_kind.findData("automatic"))
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual(self.window.catalog_model.rowCount(), 0)
        self.assertEqual(self.window.catalog_results_count.text(), "0 encontrados")

        self.window.catalog_dub_kind.setCurrentIndex(self.window.catalog_dub_kind.findData(""))
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual([item["video_id"] for item in self.window._catalog_rows], ["abc123"])
        self.assertEqual(self.window.catalog_model.rowCount(), 1)
        self.assertEqual(self.window.catalog_results_count.text(), "1 encontrados")

    def test_catalog_results_count_stays_exact_while_loading_more_pages(self) -> None:
        original_page_size = ui_module.CATALOG_PAGE_SIZE
        ui_module.CATALOG_PAGE_SIZE = 2
        try:
            for index in range(5):
                video_id = f"paged-count-{index}"
                self.repo.upsert_candidate(
                    CandidateVideo(
                        video_id=video_id,
                        title=f"Paged count video {index}",
                        channel="Paged Count",
                        channel_id="paged-count",
                        duration_seconds=100 + index,
                        thumbnail_url="",
                        source_id=self.source_id,
                        discovered_at=to_iso(),
                    )
                )
                self.repo.store_inspection_result(
                    video_id,
                    audio_languages=["en", "es-US"],
                    has_dubbing=True,
                    dub_evidence={
                        "source": "inspection",
                        "original_audio_languages": ["en"],
                        "auto_dubbed_languages": [],
                    },
                    published_at=f"2026-05-{10 + index:02d}",
                    view_count=100 + index,
                )

            self.window.switch_page("catalog")
            self.window.show()
            self.app.processEvents()
            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)
            wait_for_catalog_count_idle(self.window, self.app)

            self.assertEqual(self.window.catalog_model.rowCount(), 2)
            self.assertEqual(self.window.catalog_results_count.text(), "6 encontrados")

            self.window.load_next_catalog_page()
            wait_for_catalog_idle(self.window, self.app)

            self.assertEqual(self.window.catalog_model.rowCount(), 4)
            self.assertEqual(self.window.catalog_results_count.text(), "6 encontrados")
            self.assertFalse(self.window._catalog_count_pending)
        finally:
            ui_module.CATALOG_PAGE_SIZE = original_page_size

    def test_manual_feed_button_runs_two_hundred_candidate_expansion(self) -> None:
        worker = FakeDiscoveryWorker()
        self.services.discovery_worker = worker  # type: ignore[assignment]
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()

        self.assertEqual(self.window.catalog_manual_discovery_button.text(), "Explorar 200")
        self.window.catalog_manual_discovery_button.click()
        for _ in range(100):
            self.app.processEvents()
            if worker.calls and self.window.catalog_manual_discovery_button.isEnabled():
                break
            time.sleep(0.01)

        self.assertEqual(worker.calls, [{"candidate_limit": 200, "max_seed_discoveries": 10}])
        self.assertEqual(self.window.catalog_manual_discovery_button.text(), "Explorar 200")
        self.assertTrue(self.window.catalog_manual_discovery_button.isEnabled())

    def test_catalog_year_controls_offer_scrollable_youtube_year_range(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog_filters()

        self.assertEqual(self.window.catalog_year.itemText(0), "Cualquier año")
        self.assertEqual(self.window.catalog_after_year.itemText(0), "Sin fecha mínima")
        self.assertEqual(self.window.catalog_before_year.itemText(0), "Sin fecha máxima")
        self.assertFalse(self.window.catalog_year.isEditable())
        self.assertFalse(self.window.catalog_after_year.isEditable())
        self.assertFalse(self.window.catalog_before_year.isEditable())
        self.assertEqual(self.window.catalog_year.maxVisibleItems(), 14)
        self.assertEqual(self.window.catalog_year.itemData(1), datetime.now().year)
        self.assertEqual(self.window.catalog_year.itemData(self.window.catalog_year.count() - 1), YOUTUBE_FIRST_YEAR)
        self.assertEqual(self.window.catalog_year.itemData(1), self.window.catalog_after_year.itemData(1))

    def test_catalog_year_range_filters_work_from_selectors(self) -> None:
        self.repo.upsert_candidate(
            CandidateVideo(
                video_id="old2025",
                title="Older dubbed video",
                channel="Mark Rober",
                channel_id="chan1",
                duration_seconds=100,
                thumbnail_url="",
                source_id=self.source_id,
                discovered_at=to_iso(),
            )
        )
        self.repo.store_inspection_result(
            "old2025",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2025-11-14",
            view_count=10,
        )
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog_filters()
        self.window.catalog_lang.setCurrentIndex(max(0, self.window.catalog_lang.findData("")))

        self.window.catalog_after_year.setCurrentIndex(self.window.catalog_after_year.findData(2026))
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual({item["video_id"] for item in self.window._catalog_rows}, {"abc123"})

        self.window.catalog_after_year.setCurrentIndex(0)
        self.window.catalog_before_year.setCurrentIndex(self.window.catalog_before_year.findData(2025))
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual({item["video_id"] for item in self.window._catalog_rows}, {"old2025"})

        self.window.catalog_after_year.setCurrentIndex(self.window.catalog_after_year.findData(2025))
        self.window.catalog_before_year.setCurrentIndex(self.window.catalog_before_year.findData(2025))
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual({item["video_id"] for item in self.window._catalog_rows}, {"old2025"})

        self.window.catalog_year.setCurrentIndex(self.window.catalog_year.findData(2026))
        wait_for_catalog_idle(self.window, self.app)
        self.assertIsNone(combo_year_value(self.window.catalog_after_year))
        self.assertIsNone(combo_year_value(self.window.catalog_before_year))
        self.assertEqual({item["video_id"] for item in self.window._catalog_rows}, {"abc123"})

    def test_catalog_cards_can_toggle_favorites_and_filter_them(self) -> None:
        self.repo.upsert_candidate(
            CandidateVideo(
                video_id="plain456",
                title="Another dubbed video",
                channel="Mark Rober",
                channel_id="chan1",
                duration_seconds=100,
                thumbnail_url="",
                source_id=self.source_id,
                discovered_at=to_iso(),
            )
        )
        self.repo.store_inspection_result(
            "plain456",
            audio_languages=["en", "es-US"],
            has_dubbing=True,
            dub_evidence={"source": "inspection", "original_audio_languages": ["en"], "auto_dubbed_languages": []},
            published_at="2026-04-21",
            view_count=10,
        )
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog_filters()
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)

        self.assertEqual(self.window.catalog_model.rowCount(), 2)
        item = next(item for item in self.window._catalog_rows if item["video_id"] == "abc123")
        self.assertFalse(bool(item.get("is_favorite")))
        self.window.toggle_catalog_favorite(item, True)
        self.app.processEvents()

        favorites = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            only_favorites=True,
        )
        self.assertEqual([item["video_id"] for item in favorites], ["abc123"])

        self.window.catalog_favorites_only.setChecked(True)
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual([item["video_id"] for item in self.window._catalog_rows], ["abc123"])
        self.assertEqual(self.window.catalog_results_count.text(), "1 encontrados")
        return

        self.assertEqual(len(self.window._catalog_card_widgets), 2)
        card = next(card for card in self.window._catalog_card_widgets if card.item["video_id"] == "abc123")
        self.assertEqual(card.favorite_button.text(), "☆")
        self.assertFalse(card.favorite_button.isVisible())

        card._hovered = True
        card.sync_favorite_button()
        self.assertTrue(card.favorite_button.isVisible())
        card.favorite_button.click()
        self.app.processEvents()

        favorites = self.repo.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
            only_favorites=True,
        )
        self.assertEqual([item["video_id"] for item in favorites], ["abc123"])

        self.window.catalog_favorites_only.setChecked(True)
        self.app.processEvents()
        self.assertEqual([item["video_id"] for item in self.window._catalog_rows], ["abc123"])
        self.assertEqual(self.window.catalog_results_count.text(), "1 encontrados")

    def test_clear_filters_resets_catalog_controls(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        wait_for_catalog_idle(self.window, self.app)
        self.window.refresh_catalog_filters()

        self.window.catalog_query.setText("lava")
        self.window.catalog_lang.setCurrentIndex(max(0, self.window.catalog_lang.findData(SPANISH_LANGUAGE_FILTER)))
        self.window.catalog_visibility.setCurrentIndex(max(0, self.window.catalog_visibility.findData(False)))
        self.window.catalog_dub_kind.setCurrentIndex(max(0, self.window.catalog_dub_kind.findData("automatic")))
        self.window.catalog_sort.setCurrentIndex(max(0, self.window.catalog_sort.findData("views")))
        self.window.catalog_year.setCurrentIndex(max(0, self.window.catalog_year.findData(2026)))
        self.window.catalog_after_year.setCurrentIndex(max(0, self.window.catalog_after_year.findData(2026)))
        self.window.catalog_before_year.setCurrentIndex(max(0, self.window.catalog_before_year.findData(2026)))
        self.window.catalog_favorites_only.setChecked(True)

        self.window.clear_catalog_filters()

        self.assertEqual(self.window.catalog_query.text(), "")
        self.assertEqual(self.window.catalog_lang.currentData(), "")
        self.assertIsNone(self.window.catalog_source.currentData())
        self.assertEqual(self.window.catalog_channel.currentData(), "")
        self.assertTrue(self.window.catalog_visibility.currentData())
        self.assertEqual(self.window.catalog_dub_kind.currentData(), "")
        self.assertEqual(self.window.catalog_sort.currentData(), "recent")
        self.assertIsNone(self.window.catalog_year.currentData())
        self.assertIsNone(self.window.catalog_after_year.currentData())
        self.assertIsNone(self.window.catalog_before_year.currentData())
        self.assertFalse(self.window.catalog_favorites_only.isChecked())


class EmptyCatalogUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(APP_STYLE)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings(project_root=Path(self.temp_dir.name))
        db = Database(settings.db_path)
        db.initialize()
        repo = Repository(db)
        self.runner = FakeRunner(repo)
        services = DesktopServices(
            settings=settings,
            db=db,
            repo=repo,
            youtube=YouTubeService(settings),
            runner=self.runner,
            diagnostics=StartupDiagnostics(node_ok=True, ytdlp_ok=True, messages=[]),
        )
        self.services = services
        self.controller = AppController(services)
        self.window = MainWindow(self.controller, services)

    def tearDown(self) -> None:
        self.window.close()
        self.temp_dir.cleanup()

    def test_empty_catalog_opens_with_onboarding_only(self) -> None:
        self.window.show()
        wait_for_catalog_idle(self.window, self.app)

        self.assertEqual(self.window.pages.currentIndex(), self.window.page_index["catalog"])
        self.assertTrue(self.window.catalog_empty_stack.isVisible())
        self.assertEqual(self.window.catalog_empty_stack.currentIndex(), 0)
        self.assertFalse(self.window.catalog_controls_shell.isVisible())
        self.assertFalse(self.window.catalog_grid_host.isVisible())

    def test_primary_nav_uses_discover_and_hides_sources(self) -> None:
        self.assertIn("catalog", self.window._nav_buttons)
        self.assertEqual(self.window._nav_buttons["catalog"].text(), "Descubrir")
        self.assertNotIn("sources", self.window._nav_buttons)
        self.assertEqual(self.window.pages.currentIndex(), self.window.page_index["catalog"])

    def test_quick_submit_creates_permanent_interest_without_requiring_sources_page(self) -> None:
        worker = FakeDiscoveryWorker()
        self.services.discovery_worker = worker  # type: ignore[assignment]
        self.window.switch_page("catalog")
        self.window.catalog_empty_input.setText("@kurzgesagt")
        self.window.handle_catalog_quick_submit()
        for _ in range(100):
            self.app.processEvents()
            if worker.immediate_calls:
                break
            time.sleep(0.01)

        seeds = self.controller.list_discovery_seeds()
        self.assertEqual(len(seeds), 1)
        self.assertEqual(seeds[0]["source_type"], "channel")
        self.assertEqual(seeds[0]["value"], "https://www.youtube.com/@kurzgesagt/videos")
        self.assertEqual(worker.immediate_calls, [{"seed_id": seeds[0]["id"], "candidate_limit": 150}])
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(self.window.catalog_empty_stack.currentIndex(), 1)


if __name__ == "__main__":
    unittest.main()
