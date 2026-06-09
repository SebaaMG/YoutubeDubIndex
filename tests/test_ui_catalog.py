from __future__ import annotations

import os
import time
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QObject, QSize, Qt, Signal
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QWidget

from app import ui as ui_module
from app.config import Settings
from app.db import Database
from app.desktop_services import AppController, DesktopServices
from app.repository import SPANISH_LANGUAGE_FILTER, CandidateVideo, Repository, SourceInput, to_iso
from app.ui import (
    APP_STYLE,
    THUMBNAIL_RENDER_SCALE,
    YOUTUBE_FIRST_YEAR,
    MainWindow,
    ThumbnailService,
    combo_duration_value,
    combo_year_value,
)
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


def wait_for_ui_actions_idle(window: MainWindow, app: QApplication, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        action_threads = getattr(window, "_ui_action_threads", [])
        if not any(thread.is_alive() for thread in action_threads) and not getattr(window, "_ui_action_handlers", {}):
            app.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("UI action did not become idle")


def wait_for_window_threads_idle(window: MainWindow, app: QApplication, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    thread_attrs = [
        "_catalog_filter_threads",
        "_catalog_page_threads",
        "_summary_refresh_threads",
        "_manual_discovery_threads",
        "_interest_discovery_threads",
        "_metadata_backfill_threads",
        "_update_threads",
        "_catalog_count_threads",
        "_active_run_snapshot_threads",
        "_ui_action_threads",
    ]
    while time.time() < deadline:
        app.processEvents()
        pending_handlers = bool(getattr(window, "_ui_action_handlers", {}))
        alive = [
            thread
            for attr in thread_attrs
            for thread in getattr(window, attr, [])
            if thread.is_alive()
        ]
        if not alive and not pending_handlers:
            return
        time.sleep(0.01)


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


class FakeProgressWorkerClient:
    def __init__(self, events: list[dict[str, object]], active_run_id: int | None = None) -> None:
        self.events = list(events)
        self._active_run_id = active_run_id

    def active_run_id(self) -> int | None:
        return self._active_run_id

    def drain_events(self, *, limit: int = 50) -> list[dict[str, object]]:
        batch = self.events[:limit]
        self.events = self.events[limit:]
        return batch


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
        wait_for_window_threads_idle(self.window, self.app)
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

    def test_topbar_has_automatic_search_toggle(self) -> None:
        toggles = [
            checkbox
            for checkbox in self.window.findChildren(QCheckBox)
            if checkbox.text() == "Búsqueda Automática"
        ]

        self.assertEqual(len(toggles), 1)
        self.assertIs(toggles[0], self.window.automatic_discovery_toggle)
        self.assertTrue(toggles[0].isChecked())

    def test_worker_progress_events_update_topbar_without_waiting_for_snapshot(self) -> None:
        self.services.worker_client = FakeProgressWorkerClient(
            [
                {
                    "event": "run_progress",
                    "run_id": 7,
                    "scope": "metadata",
                    "videos_checked": 50,
                    "candidates_found": 250,
                    "dubbed_found": 42,
                }
            ],
            active_run_id=7,
        )  # type: ignore[assignment]
        self.window.show()
        self.app.processEvents()

        self.window._drain_worker_events()

        self.assertTrue(self.window.topbar_progress.isVisible())
        self.assertEqual(self.window.topbar_progress.maximum(), 250)
        self.assertEqual(self.window.topbar_progress.value(), 50)
        self.assertIn("50/250", self.window.topbar_status_label.text())
        self.assertIn("42 doblados", self.window.topbar_status_label.text())

    def test_discovery_progress_events_update_topbar_every_chunk(self) -> None:
        self.services.worker_client = FakeProgressWorkerClient(
            [
                {
                    "event": "discovery_progress",
                    "target": 250,
                    "inspected": 100,
                    "verified": 63,
                    "failed": 1,
                }
            ]
        )  # type: ignore[assignment]
        self.window.show()
        self.app.processEvents()

        self.window._drain_worker_events()

        self.assertTrue(self.window.topbar_progress.isVisible())
        self.assertEqual(self.window.topbar_progress.maximum(), 250)
        self.assertEqual(self.window.topbar_progress.value(), 100)
        self.assertIn("100/250", self.window.topbar_status_label.text())
        self.assertIn("63 doblados", self.window.topbar_status_label.text())

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
        self.assertIsInstance(self.window.catalog_lang, ui_module.CatalogFilterComboBox)
        self.assertIsInstance(self.window.catalog_sort, ui_module.CatalogFilterComboBox)
        self.assertEqual(self.window.catalog_lang.display_text(), "Idioma: Español")
        self.assertEqual(self.window.catalog_sort.display_text(), "Ordenar por: Más recientes")
        self.assertEqual(self.window.catalog_sort.currentText(), "Más recientes")
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

    def test_secondary_catalog_filters_use_dropdown_controls(self) -> None:
        combos = (
            self.window.catalog_channel,
            self.window.catalog_source,
            self.window.catalog_visibility,
            self.window.catalog_dub_kind,
            self.window.catalog_year,
            self.window.catalog_after_year,
            self.window.catalog_before_year,
            self.window.catalog_max_duration,
        )

        self.assertTrue(all(isinstance(combo, ui_module.CatalogFilterComboBox) for combo in combos))

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

    def test_thumbnail_render_scale_uses_full_card_resolution(self) -> None:
        self.assertEqual(THUMBNAIL_RENDER_SCALE, 1.0)

    def test_youtube_thumbnail_candidates_add_stable_fallbacks(self) -> None:
        stale_url = "https://i.ytimg.com/vi/ueSrDmm5X5Y/hq720_custom_2.jpg?expired=1"

        candidates = ui_module.youtube_thumbnail_candidates("ueSrDmm5X5Y", stale_url)

        self.assertEqual(candidates[0], stale_url)
        self.assertIn("https://i.ytimg.com/vi/ueSrDmm5X5Y/hq720.jpg", candidates)
        self.assertIn("https://i.ytimg.com/vi/ueSrDmm5X5Y/hqdefault.jpg", candidates)
        self.assertEqual(len(candidates), len(set(candidates)))

    def test_thumbnail_service_tries_next_fallback_when_request_fails(self) -> None:
        class FakeReply(QObject):
            finished = Signal()

            def __init__(self, error: QNetworkReply.NetworkError) -> None:
                super().__init__()
                self._error = error
                self.deleted = False

            def error(self) -> QNetworkReply.NetworkError:
                return self._error

            def readAll(self) -> bytes:
                return b""

            def deleteLater(self) -> None:
                self.deleted = True

        class FakeManager:
            def __init__(self) -> None:
                self.urls: list[str] = []
                self.replies: list[FakeReply] = []

            def get(self, request: object) -> FakeReply:
                url_getter = getattr(request, "url")
                self.urls.append(url_getter().toString())
                error = (
                    QNetworkReply.NetworkError.ContentNotFoundError
                    if len(self.urls) == 1
                    else QNetworkReply.NetworkError.NoError
                )
                reply = FakeReply(error)
                self.replies.append(reply)
                return reply

        owner = QWidget()
        service = ThumbnailService(owner, Path(self.temp_dir.name) / "thumbs")
        fake_manager = FakeManager()
        service.manager = fake_manager  # type: ignore[assignment]

        service.request_with_fallbacks(
            ["https://example.test/stale.jpg", "https://example.test/stable.jpg"],
            QSize(96, 54),
            lambda _pixmap: None,
        )
        fake_manager.replies[0].finished.emit()
        for _ in range(20):
            self.app.processEvents()
            if len(fake_manager.urls) >= 2:
                break
            time.sleep(0.01)

        self.assertEqual(fake_manager.urls, ["https://example.test/stale.jpg", "https://example.test/stable.jpg"])
        self.assertTrue(fake_manager.replies[0].deleted)
        service.shutdown()

    def test_catalog_card_height_is_compact_without_changing_thumbnail_ratio(self) -> None:
        delegate = ui_module.CatalogCardDelegate()

        delegate.configure(300, "Medio")

        self.assertEqual(delegate.thumbnail_height(), round(300 * 9 / 16))
        self.assertLessEqual(delegate.card_height - delegate.thumbnail_height(), 106)
        self.assertLess(delegate.card_height, 280)

    def test_catalog_wheel_scroll_uses_small_pixel_steps(self) -> None:
        delegate = ui_module.CatalogCardDelegate()
        view = ui_module.CatalogListView(delegate)
        bar = view.verticalScrollBar()
        bar.setRange(0, 1000)
        bar.setValue(500)

        event = QWheelEvent(
            QPointF(20, 20),
            QPointF(20, 20),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        view.wheelEvent(event)

        self.assertEqual(bar.value(), 572)
        self.assertTrue(event.isAccepted())

    def test_thumbnail_service_caps_active_network_requests(self) -> None:
        class FakeReply(QObject):
            finished = Signal()

        class FakeManager:
            def __init__(self) -> None:
                self.urls: list[str] = []
                self.replies: list[FakeReply] = []

            def get(self, request: object) -> FakeReply:
                url_getter = getattr(request, "url")
                self.urls.append(url_getter().toString())
                reply = FakeReply()
                self.replies.append(reply)
                return reply

        owner = QWidget()
        service = ThumbnailService(owner, Path(self.temp_dir.name) / "thumbs")
        fake_manager = FakeManager()
        service.manager = fake_manager  # type: ignore[assignment]

        for index in range(20):
            service.request(
                f"https://example.test/thumb-{index}.jpg",
                QSize(96, 54),
                lambda _pixmap: None,
            )

        self.assertEqual(len(fake_manager.urls), 6)
        self.assertLessEqual(getattr(service, "active_request_count")(), 6)
        service.shutdown()

    def test_thumbnail_shutdown_aborts_active_replies(self) -> None:
        class FakeReply:
            def __init__(self) -> None:
                self.aborted = False
                self.deleted = False

            def abort(self) -> None:
                self.aborted = True

            def deleteLater(self) -> None:
                self.deleted = True

        owner = QWidget()
        service = ThumbnailService(owner, Path(self.temp_dir.name) / "thumbs")
        reply = FakeReply()
        service._active_replies[("https://example.test/thumb.jpg", 96, 54)] = reply  # type: ignore[assignment]

        service.shutdown()

        self.assertTrue(reply.aborted)
        self.assertTrue(reply.deleted)

    def test_model_batches_thumbnail_updates_into_contiguous_ranges(self) -> None:
        model = ui_module.CatalogListModel()
        model.set_items(
            [
                {"video_id": "a", "thumbnail_url": "one"},
                {"video_id": "b", "thumbnail_url": "one"},
                {"video_id": "c", "thumbnail_url": "skip"},
                {"video_id": "d", "thumbnail_url": "two"},
            ]
        )
        emissions: list[tuple[int, int]] = []
        model.dataChanged.connect(lambda top, bottom, _roles: emissions.append((top.row(), bottom.row())))
        pixmap = QPixmap(4, 4)
        pixmap.fill()

        model.set_thumbnails_batch({"one": pixmap, "two": pixmap})

        self.assertEqual(emissions, [(0, 1), (3, 3)])

    def test_model_can_attach_fallback_thumbnail_url_to_empty_item(self) -> None:
        model = ui_module.CatalogListModel()
        model.set_items([{"video_id": "missing-url", "thumbnail_url": ""}])
        pixmap = QPixmap(4, 4)
        pixmap.fill()

        model.set_thumbnail_url(0, "https://i.ytimg.com/vi/missing-url/hq720.jpg")
        model.set_thumbnails_batch({"https://i.ytimg.com/vi/missing-url/hq720.jpg": pixmap})

        loaded = model.data(model.index(0, 0), ui_module.CATALOG_PIXMAP_ROLE)
        self.assertIsInstance(loaded, QPixmap)
        self.assertFalse(loaded.isNull())

    def test_stale_catalog_thumbnails_do_not_emit_model_changes(self) -> None:
        self.window.catalog_model.set_items(
            [
                {"video_id": "visible", "thumbnail_url": "visible-url"},
                {"video_id": "stale", "thumbnail_url": "stale-url"},
            ]
        )
        emissions: list[tuple[int, int]] = []
        self.window.catalog_model.dataChanged.connect(
            lambda top, bottom, _roles: emissions.append((top.row(), bottom.row()))
        )
        self.window._catalog_visible_thumbnail_urls = {"visible-url"}
        pixmap = QPixmap(4, 4)
        pixmap.fill()

        self.window.apply_catalog_thumbnail("stale-url", pixmap, self.window._catalog_query_generation)

        self.assertEqual(emissions, [])

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

    def test_catalog_append_keeps_scroll_position_across_rerender(self) -> None:
        original_page_size = ui_module.CATALOG_PAGE_SIZE
        ui_module.CATALOG_PAGE_SIZE = 20
        try:
            for index in range(60):
                video_id = f"scroll-page-{index:02d}"
                self.repo.upsert_candidate(
                    CandidateVideo(
                        video_id=video_id,
                        title=f"Scroll page video {index}",
                        channel="Scroll Channel",
                        channel_id="scroll-channel",
                        duration_seconds=90 + index,
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
                    published_at=f"2026-04-{(index % 28) + 1:02d}",
                    view_count=1000 + index,
                )

            self.window.resize(900, 500)
            self.window.switch_page("catalog")
            self.window.show()
            self.app.processEvents()
            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)

            bar = self.window.catalog_view.verticalScrollBar()
            bar.setValue(max(1, bar.maximum() - 20))
            self.app.processEvents()
            before_append = bar.value()

            self.window.load_next_catalog_page()
            wait_for_catalog_idle(self.window, self.app)
            after_append = bar.value()
            self.window.render_catalog_cards()
            self.app.processEvents()

            self.assertGreater(before_append, 0)
            self.assertGreaterEqual(after_append, before_append - 1)
            self.assertGreaterEqual(bar.value(), before_append - 1)
        finally:
            ui_module.CATALOG_PAGE_SIZE = original_page_size

    def test_catalog_rerender_with_same_rows_does_not_reset_model(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)

        resets: list[bool] = []
        self.window.catalog_model.modelReset.connect(lambda: resets.append(True))

        self.window.render_catalog_cards()
        self.app.processEvents()

        self.assertEqual(resets, [])

    def test_catalog_near_bottom_append_does_not_jump_to_top(self) -> None:
        original_page_size = ui_module.CATALOG_PAGE_SIZE
        ui_module.CATALOG_PAGE_SIZE = 20
        try:
            for index in range(60):
                video_id = f"near-bottom-{index:02d}"
                self.repo.upsert_candidate(
                    CandidateVideo(
                        video_id=video_id,
                        title=f"Near bottom video {index}",
                        channel="Near Bottom",
                        channel_id="near-bottom",
                        duration_seconds=90 + index,
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
                    published_at=f"2026-02-{(index % 28) + 1:02d}",
                    view_count=1000 + index,
                )

            self.window.resize(900, 500)
            self.window.switch_page("catalog")
            self.window.show()
            self.app.processEvents()
            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)

            bar = self.window.catalog_view.verticalScrollBar()
            bar.setValue(bar.maximum())
            wait_for_catalog_idle(self.window, self.app)
            self.app.processEvents()

            self.assertGreater(bar.maximum(), 0)
            self.assertEqual(self.window.catalog_model.rowCount(), 40)
            self.assertEqual(bar.value(), bar.maximum())
        finally:
            ui_module.CATALOG_PAGE_SIZE = original_page_size

    def test_catalog_large_append_stays_at_bottom_after_batched_layout_settles(self) -> None:
        original_page_size = ui_module.CATALOG_PAGE_SIZE
        ui_module.CATALOG_PAGE_SIZE = 80
        try:
            for index in range(220):
                video_id = f"batched-bottom-{index:03d}"
                self.repo.upsert_candidate(
                    CandidateVideo(
                        video_id=video_id,
                        title=f"Batched bottom video {index}",
                        channel="Batched Bottom",
                        channel_id="batched-bottom",
                        duration_seconds=90 + index,
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
                    published_at=f"2026-05-{(index % 28) + 1:02d}",
                    view_count=1000 + index,
                )

            self.window.resize(900, 500)
            self.window.switch_page("catalog")
            self.window.show()
            self.app.processEvents()
            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)
            for _ in range(20):
                self.app.processEvents()
                time.sleep(0.001)

            bar = self.window.catalog_view.verticalScrollBar()
            bar.setValue(bar.maximum())
            self.app.processEvents()

            self.window.load_next_catalog_page()
            wait_for_catalog_idle(self.window, self.app)
            for _ in range(40):
                self.app.processEvents()
                time.sleep(0.001)

            self.assertGreaterEqual(self.window.catalog_model.rowCount(), 160)
            self.assertGreater(bar.maximum(), 0)
            self.assertEqual(bar.value(), bar.maximum())
        finally:
            ui_module.CATALOG_PAGE_SIZE = original_page_size

    def test_catalog_same_filter_refresh_keeps_scroll_position(self) -> None:
        original_page_size = ui_module.CATALOG_PAGE_SIZE
        ui_module.CATALOG_PAGE_SIZE = 80
        try:
            for index in range(60):
                video_id = f"refresh-scroll-{index:02d}"
                self.repo.upsert_candidate(
                    CandidateVideo(
                        video_id=video_id,
                        title=f"Refresh scroll video {index}",
                        channel="Refresh Scroll",
                        channel_id="refresh-scroll",
                        duration_seconds=90 + index,
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
                    published_at=f"2026-03-{(index % 28) + 1:02d}",
                    view_count=1000 + index,
                )

            self.window.resize(900, 500)
            self.window.switch_page("catalog")
            self.window.show()
            self.app.processEvents()
            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)

            bar = self.window.catalog_view.verticalScrollBar()
            bar.setValue(max(1, bar.maximum() // 2))
            self.app.processEvents()
            before_refresh = bar.value()

            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)

            self.assertGreater(before_refresh, 0)
            self.assertGreaterEqual(bar.value(), before_refresh - 1)
        finally:
            ui_module.CATALOG_PAGE_SIZE = original_page_size

    def test_catalog_same_filter_refresh_keeps_loaded_pages(self) -> None:
        original_page_size = ui_module.CATALOG_PAGE_SIZE
        ui_module.CATALOG_PAGE_SIZE = 20
        try:
            for index in range(60):
                video_id = f"loaded-refresh-{index:02d}"
                self.repo.upsert_candidate(
                    CandidateVideo(
                        video_id=video_id,
                        title=f"Loaded refresh video {index}",
                        channel="Loaded Refresh",
                        channel_id="loaded-refresh",
                        duration_seconds=90 + index,
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
                    published_at=f"2026-01-{(index % 28) + 1:02d}",
                    view_count=1000 + index,
                )

            self.window.resize(900, 500)
            self.window.switch_page("catalog")
            self.window.show()
            self.app.processEvents()
            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)
            self.window.load_next_catalog_page()
            wait_for_catalog_idle(self.window, self.app)

            bar = self.window.catalog_view.verticalScrollBar()
            bar.setValue(max(1, bar.maximum() // 2))
            self.app.processEvents()
            before_refresh = bar.value()

            self.assertEqual(self.window.catalog_model.rowCount(), 40)

            calls: list[dict[str, object]] = []

            def fake_start_catalog_page_worker(generation: int, filters: dict[str, object], **kwargs: object) -> None:
                calls.append(
                    {
                        "generation": generation,
                        "filters": dict(filters),
                        "cursor": kwargs.get("cursor"),
                        "append": kwargs.get("append"),
                        "page_size": kwargs.get("page_size"),
                    }
                )

            self.window.start_catalog_page_worker = fake_start_catalog_page_worker  # type: ignore[method-assign]
            self.window.refresh_catalog()

            self.assertEqual(self.window.catalog_model.rowCount(), 40)
            self.assertEqual(len(calls), 1)
            self.assertFalse(calls[0]["append"])
            self.assertEqual(calls[0]["page_size"], 40)
            self.assertGreaterEqual(bar.value(), before_refresh - 1)
        finally:
            ui_module.CATALOG_PAGE_SIZE = original_page_size

    def test_catalog_same_filter_refresh_waits_for_pending_append(self) -> None:
        original_page_size = ui_module.CATALOG_PAGE_SIZE
        ui_module.CATALOG_PAGE_SIZE = 20
        try:
            for index in range(60):
                video_id = f"append-refresh-{index:02d}"
                self.repo.upsert_candidate(
                    CandidateVideo(
                        video_id=video_id,
                        title=f"Append refresh video {index}",
                        channel="Append Refresh",
                        channel_id="append-refresh",
                        duration_seconds=90 + index,
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
                    published_at=f"2026-01-{(index % 28) + 1:02d}",
                    view_count=1000 + index,
                )

            self.window.resize(900, 500)
            self.window.switch_page("catalog")
            self.window.show()
            self.app.processEvents()
            self.window.refresh_catalog()
            wait_for_catalog_idle(self.window, self.app)

            calls: list[dict[str, object]] = []

            def fake_start_catalog_page_worker(generation: int, filters: dict[str, object], **kwargs: object) -> None:
                calls.append(
                    {
                        "generation": generation,
                        "filters": dict(filters),
                        "cursor": kwargs.get("cursor"),
                        "append": kwargs.get("append"),
                        "page_size": kwargs.get("page_size"),
                    }
                )

            self.window.start_catalog_page_worker = fake_start_catalog_page_worker  # type: ignore[method-assign]
            bar = self.window.catalog_view.verticalScrollBar()
            bar.setValue(bar.maximum())
            self.app.processEvents()

            self.window.load_next_catalog_page()
            append_generation = self.window._catalog_query_generation
            self.assertEqual(len(calls), 1)
            self.assertTrue(calls[0]["append"])

            self.window.refresh_catalog()

            self.assertEqual(len(calls), 1)
            self.assertEqual(self.window._catalog_query_generation, append_generation)

            page = self.window.controller.list_catalog_page(
                lang=calls[0]["filters"].get("lang"),
                source_id=calls[0]["filters"].get("source_id"),
                channel=calls[0]["filters"].get("channel"),
                query=calls[0]["filters"].get("query"),
                only_dubbed=bool(calls[0]["filters"].get("only_dubbed")),
                only_favorites=bool(calls[0]["filters"].get("only_favorites")),
                dub_kind=str(calls[0]["filters"].get("dub_kind") or ""),
                sort_by=str(calls[0]["filters"].get("sort_by") or "recent"),
                year=calls[0]["filters"].get("year"),
                year_after=calls[0]["filters"].get("year_after"),
                year_before=calls[0]["filters"].get("year_before"),
                max_duration_seconds=calls[0]["filters"].get("max_duration_seconds"),
                page_size=ui_module.CATALOG_PAGE_SIZE,
                cursor=str(calls[0]["cursor"]),
            )
            self.window.handle_catalog_page_ready(append_generation, page, True)
            self.app.processEvents()

            self.assertEqual(self.window.catalog_model.rowCount(), 40)
            self.assertEqual(len(calls), 2)
            self.assertFalse(calls[1]["append"])
            self.assertEqual(calls[1]["page_size"], 40)
        finally:
            ui_module.CATALOG_PAGE_SIZE = original_page_size

    def test_manual_feed_button_runs_two_hundred_fifty_candidate_expansion(self) -> None:
        worker = FakeDiscoveryWorker()
        self.services.discovery_worker = worker  # type: ignore[assignment]
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()

        self.assertEqual(self.window.catalog_manual_discovery_button.text(), "Explorar 250")
        self.window.catalog_manual_discovery_button.click()
        for _ in range(100):
            self.app.processEvents()
            if worker.calls and self.window.catalog_manual_discovery_button.isEnabled():
                break
            time.sleep(0.01)

        self.assertEqual(worker.calls, [{"candidate_limit": 250, "max_seed_discoveries": None}])
        self.assertEqual(self.window.catalog_manual_discovery_button.text(), "Explorar 250")
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

    def test_catalog_max_duration_filter_options_and_query(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)

        self.assertEqual(self.window.catalog_max_duration.itemText(0), "Cualquier duración")
        self.assertEqual(
            [
                self.window.catalog_max_duration.itemData(index)
                for index in range(1, self.window.catalog_max_duration.count())
            ],
            [minutes * 60 for minutes in range(10, 61, 10)],
        )

        self.window.catalog_max_duration.setCurrentIndex(self.window.catalog_max_duration.findData(10 * 60))
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual(self.window.catalog_model.rowCount(), 0)

        self.window.catalog_max_duration.setCurrentIndex(self.window.catalog_max_duration.findData(30 * 60))
        wait_for_catalog_idle(self.window, self.app)
        self.assertEqual([item["video_id"] for item in self.window._catalog_rows], ["abc123"])
        self.assertEqual(combo_duration_value(self.window.catalog_max_duration), 30 * 60)

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
        wait_for_ui_actions_idle(self.window, self.app)
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
        self.window.catalog_max_duration.setCurrentIndex(max(0, self.window.catalog_max_duration.findData(30 * 60)))
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
        self.assertIsNone(self.window.catalog_max_duration.currentData())
        self.assertFalse(self.window.catalog_favorites_only.isChecked())

    def test_favorite_toggle_is_optimistic_and_rolls_back_on_error(self) -> None:
        self.window.switch_page("catalog")
        self.window.show()
        self.app.processEvents()
        self.window.refresh_catalog()
        wait_for_catalog_idle(self.window, self.app)
        item = next(item for item in self.window._catalog_rows if item["video_id"] == "abc123")
        errors: list[tuple[str, str]] = []

        def failing_set_favorite(_video_id: str, _is_favorite: bool) -> None:
            raise RuntimeError("database busy")

        self.controller.set_video_favorite = failing_set_favorite  # type: ignore[method-assign]
        self.window.show_error = lambda title, error: errors.append((title, str(error)))  # type: ignore[method-assign]

        started = time.perf_counter()
        self.window.toggle_catalog_favorite(item, True)
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.05)
        self.assertTrue(bool(item.get("is_favorite")))
        wait_for_ui_actions_idle(self.window, self.app)

        self.assertFalse(bool(item.get("is_favorite")))
        self.assertEqual(errors, [("No se pudo actualizar el favorito", "database busy")])


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
        wait_for_window_threads_idle(self.window, self.app)
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
