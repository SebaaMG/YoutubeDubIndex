from __future__ import annotations

import os
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication, QPushButton

from app.config import Settings
from app.db import Database
from app.desktop_services import AppController, DesktopServices
from app.repository import CandidateVideo, Repository, to_iso
from app.ui import (
    APP_STYLE,
    FULL_SOURCE_STATE,
    SOURCE_COMBO_STYLE,
    SOURCE_PRIMARY_BUTTON_STYLE,
    MainWindow,
    SourceComboBox,
    SourceSpinBox,
)
from app.youtube import StartupDiagnostics, YouTubeService


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


class SourceUiTests(unittest.TestCase):
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
        self.controller = AppController(services)
        self.window = MainWindow(self.controller, services)
        self.repo = repo

    def tearDown(self) -> None:
        self.wait_for_window_threads_idle()
        self.window.close()
        self.temp_dir.cleanup()

    def wait_for_window_threads_idle(self, timeout: float = 3.0) -> None:
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
            self.app.processEvents()
            pending_handlers = bool(getattr(self.window, "_ui_action_handlers", {}))
            alive = [
                thread
                for attr in thread_attrs
                for thread in getattr(self.window, attr, [])
                if thread.is_alive()
            ]
            if not alive and not pending_handlers:
                return
            time.sleep(0.01)

    def wait_for_ui_actions_idle(self, timeout: float = 3.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.processEvents()
            action_threads = getattr(self.window, "_ui_action_threads", [])
            if not any(thread.is_alive() for thread in action_threads) and not getattr(self.window, "_ui_action_handlers", {}):
                self.app.processEvents()
                return
            time.sleep(0.01)
        raise AssertionError("UI action did not become idle")

    def test_selecting_row_does_not_auto_enter_edit_mode(self) -> None:
        self.controller.create_source(
            source_type="channel",
            label="kurzgesagt",
            value="kurzgesagt",
            max_candidates_per_run=50,
            enabled=True,
        )
        self.window.refresh_sources()

        self.window.sources_table.selectRow(0)

        self.assertIsNone(self.window._editing_source_id)
        self.assertEqual(self.window.source_form_card.title_label.text(), "Nueva búsqueda")
        self.assertEqual(self.window.source_save_button.text(), "Guardar búsqueda")

    def test_can_create_search_source_while_channel_row_is_selected(self) -> None:
        self.controller.create_source(
            source_type="channel",
            label="kurzgesagt",
            value="kurzgesagt",
            max_candidates_per_run=50,
            enabled=True,
        )
        self.window.refresh_sources()
        self.window.sources_table.selectRow(0)
        self.window.open_sources_advanced()

        self.window.source_type.setCurrentIndex(self.window.source_type.findData("search"))
        self.window.source_value.setText("kurzgesagt space")
        self.window.source_max_candidates.setValue(25)
        self.window.save_source()
        self.wait_for_ui_actions_idle()

        sources = self.controller.list_sources()
        self.assertEqual(len(sources), 2)
        self.assertEqual({source["type"] for source in sources}, {"channel", "search"})
        self.assertIn("kurzgesagt space", {source["label"] for source in sources if source["type"] == "search"})
        self.assertEqual(len(self.runner.calls), 1)
        self.assertEqual(self.runner.calls[0]["kwargs"]["scope"], "source:2")
        self.assertEqual(self.runner.calls[0]["kwargs"]["source_id"], 2)

    def test_edit_selected_button_enters_edit_mode_explicitly(self) -> None:
        self.controller.create_source(
            source_type="channel",
            label="kurzgesagt",
            value="kurzgesagt",
            max_candidates_per_run=50,
            enabled=True,
        )
        self.window.refresh_sources()
        self.window.sources_table.selectRow(0)

        self.window.edit_selected_source()

        self.assertIsNotNone(self.window._editing_source_id)
        self.assertFalse(self.window.source_advanced_box.isHidden())
        self.assertEqual(self.window.source_form_card.title_label.text(), "Editar búsqueda #1")
        self.assertEqual(self.window.source_save_button.text(), "Guardar cambios")
        self.assertFalse(self.window.source_cancel_edit_button.isHidden())

    def test_cancel_edit_button_returns_to_new_source_mode_without_saving(self) -> None:
        source_id = self.controller.create_source(
            source_type="channel",
            label="kurzgesagt",
            value="kurzgesagt",
            max_candidates_per_run=50,
            enabled=True,
        )
        self.window.refresh_sources()
        self.window.sources_table.selectRow(0)
        self.window.edit_selected_source()
        self.window.source_value.setText("changed-value")

        self.window.cancel_source_edit()

        self.assertIsNone(self.window._editing_source_id)
        self.assertEqual(self.window.source_form_card.title_label.text(), "Nueva búsqueda")
        self.assertEqual(self.window.source_save_button.text(), "Guardar búsqueda")
        self.assertTrue(self.window.source_cancel_edit_button.isHidden())
        self.assertEqual(self.window.source_value.text(), "")
        source = self.controller.services.repo.get_source(source_id)
        self.assertIsNotNone(source)
        assert source is not None
        self.assertEqual(source["value"], "https://www.youtube.com/@kurzgesagt/videos")
        self.assertNotEqual(source["value"], "changed-value")
        self.assertEqual(len(self.runner.calls), 0)

    def test_quick_source_creation_uses_empty_catalog_field_and_creates_interest(self) -> None:
        self.window.catalog_empty_input.setText("@kurzgesagt")
        self.window.handle_catalog_quick_submit()
        self.wait_for_ui_actions_idle()

        seeds = self.controller.list_discovery_seeds()
        self.assertEqual(len(seeds), 1)
        self.assertEqual(seeds[0]["source_type"], "channel")
        self.assertEqual(seeds[0]["value"], "https://www.youtube.com/@kurzgesagt/videos")
        self.assertEqual(self.runner.calls, [])

    def test_toggle_button_reflects_selected_source_state(self) -> None:
        source_id = self.controller.create_source(
            source_type="search",
            label="demo",
            value="demo",
            max_candidates_per_run=50,
            enabled=False,
        )
        self.window.refresh_sources()
        row = next(index for index, source in enumerate(self.controller.list_sources()) if source["id"] == source_id)
        self.window.sources_table.selectRow(row)
        self.app.processEvents()

        self.assertEqual(self.window.source_toggle_button.text(), "Reactivar")

    def test_full_sources_show_limit_button_and_bulk_increase(self) -> None:
        full_a = self.controller.create_source(
            source_type="search",
            label="full a",
            value="full a",
            max_candidates_per_run=2,
            enabled=True,
        )
        full_b = self.controller.create_source(
            source_type="search",
            label="full b",
            value="full b",
            max_candidates_per_run=1,
            enabled=True,
        )
        partial = self.controller.create_source(
            source_type="search",
            label="partial",
            value="partial",
            max_candidates_per_run=3,
            enabled=True,
        )
        self.repo.upsert_candidate(CandidateVideo("a1", "A1", "Chan", "chan1", 100, None, full_a, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("a2", "A2", "Chan", "chan1", 100, None, full_a, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("b1", "B1", "Chan", "chan1", 100, None, full_b, to_iso()))
        self.repo.upsert_candidate(CandidateVideo("c1", "C1", "Chan", "chan1", 100, None, partial, to_iso()))

        self.window.refresh_sources()

        states = [self.window.sources_table.item(row, 3).text() for row in range(self.window.sources_table.rowCount())]
        self.assertIn(FULL_SOURCE_STATE, states)
        self.assertFalse(self.window.source_increase_limit_button.isHidden())

        self.window.increase_full_source_limits()
        self.wait_for_ui_actions_idle()

        sources_by_id = {int(source["id"]): source for source in self.controller.list_sources()}
        self.assertEqual(sources_by_id[full_a]["max_candidates_per_run"], 502)
        self.assertEqual(sources_by_id[full_b]["max_candidates_per_run"], 501)
        self.assertEqual(sources_by_id[partial]["max_candidates_per_run"], 3)
        self.assertTrue(self.window.source_increase_limit_button.isHidden())

    def test_sources_page_keeps_only_saved_sources_surface_visible(self) -> None:
        self.window.switch_page("sources")
        self.window.show()
        self.app.processEvents()

        self.assertFalse(self.window.sources_recent_runs_table.isVisible())
        self.assertFalse(self.window.sources_full_history_table.isVisible())
        self.assertFalse(self.window.sources_history_toggle.isVisible())

    def test_sources_page_keeps_side_by_side_layout_without_clipping_controls(self) -> None:
        self.window.show()
        self.window.resize(1680, 943)
        self.window.switch_page("sources")
        self.app.processEvents()
        self.app.processEvents()

        self.assertEqual(self.window._sources_layout_mode, "wide")
        form_row, form_column, _, _ = self.window.sources_layout.getItemPosition(
            self.window.sources_layout.indexOf(self.window.source_form_card)
        )
        table_row, table_column, _, _ = self.window.sources_layout.getItemPosition(
            self.window.sources_layout.indexOf(self.window.sources_right_host)
        )
        self.assertEqual(form_row, table_row)
        self.assertLess(form_column, table_column)

        viewport = self.window.sources_scroll.viewport().rect()
        save_bottom = self.window.source_save_button.mapTo(
            self.window.sources_scroll.viewport(), self.window.source_save_button.rect().bottomRight()
        )
        self.assertLessEqual(save_bottom.y(), viewport.height())

        delete_bottom = self.window.source_delete_button.mapTo(
            self.window.sources_scroll.viewport(), self.window.source_delete_button.rect().bottomRight()
        )
        self.assertLessEqual(delete_bottom.x(), self.window.sources_scroll.viewport().rect().width())

        self.window.resize(1280, 720)
        self.app.processEvents()
        self.assertEqual(self.window.width(), 1280)
        self.assertLessEqual(self.window.sources_page.width(), self.window.sources_scroll.viewport().width())
        self.assertEqual(self.window.sources_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)
        self.assertEqual(self.window.sources_scroll.verticalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)

    def test_source_controls_are_visually_marked_as_interactive(self) -> None:
        for control in (self.window.source_type, self.window.source_value, self.window.source_max_candidates):
            self.assertEqual(control.property("compactSource"), "true")

        self.assertIsInstance(self.window.source_type, SourceComboBox)
        self.assertIsInstance(self.window.source_max_candidates, SourceSpinBox)
        self.assertIn("#526b85", self.window.source_type.styleSheet())
        self.assertIn("drop-down", self.window.source_type.styleSheet())
        self.assertIn("up-button", self.window.source_max_candidates.styleSheet())

        for button in (
            self.window.source_edit_button,
            self.window.source_toggle_button,
            self.window.source_delete_button,
        ):
            self.assertEqual(button.property("sourceAction"), "true")
            self.assertIn("#52687f", button.styleSheet())
            self.assertIn(":disabled", button.styleSheet())

        self.assertEqual(self.window.source_save_button.property("sourcePrimary"), "true")
        self.assertIn("#237dee", self.window.source_save_button.styleSheet())
        self.assertIn('QPushButton[sourceAction="true"]', APP_STYLE)
        self.assertIn('QLineEdit[compactSource="true"]', APP_STYLE)
        self.assertIn("drop-down", SOURCE_COMBO_STYLE)
        self.assertIn(":disabled", SOURCE_PRIMARY_BUTTON_STYLE)

    def test_manual_run_buttons_are_not_shown(self) -> None:
        button_texts = [button.text() for button in self.window.findChildren(QPushButton)]

        self.assertNotIn("Buscar ahora", button_texts)
        self.assertNotIn("Escanear seleccionada", button_texts)
        self.assertFalse(hasattr(self.window, "source_run_button"))

    def test_source_copy_changes_with_type(self) -> None:
        self.window.source_type.setCurrentIndex(self.window.source_type.findData("channel"))
        self.assertEqual(self.window.source_value_label.text(), "Canal")
        self.assertIn("@canal", self.window.source_value.placeholderText())

        self.window.source_type.setCurrentIndex(self.window.source_type.findData("search"))
        self.assertEqual(self.window.source_value_label.text(), "Búsqueda")
        self.assertIn("término", self.window.source_value.placeholderText())

    def test_last_max_candidates_is_remembered_after_save(self) -> None:
        self.window.source_type.setCurrentIndex(self.window.source_type.findData("search"))
        self.window.source_value.setText("anime latino")
        self.window.source_max_candidates.setValue(3456)
        self.window.save_source()
        self.wait_for_ui_actions_idle()

        self.assertEqual(self.controller.get_last_max_candidates(), 3456)
        self.assertEqual(self.window.source_max_candidates.value(), 3456)
        self.assertEqual(len(self.runner.calls), 1)
        self.assertEqual(self.runner.calls[0]["kwargs"]["scope"], "source:1")

    def test_save_source_runs_controller_work_off_ui_thread(self) -> None:
        original_create_source = self.controller.create_source

        def slow_create_source(*args: object, **kwargs: object) -> int:
            time.sleep(0.15)
            return original_create_source(*args, **kwargs)

        self.controller.create_source = slow_create_source  # type: ignore[method-assign]
        self.window.source_type.setCurrentIndex(self.window.source_type.findData("search"))
        self.window.source_value.setText("slow source")

        started = time.perf_counter()
        self.window.save_source()
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.08)
        self.assertFalse(self.window.source_save_button.isEnabled())
        self.wait_for_ui_actions_idle()
        self.assertTrue(self.window.source_save_button.isEnabled())
        self.assertEqual(len(self.controller.list_sources()), 1)

    def test_enter_in_source_value_saves_source(self) -> None:
        self.window.source_type.setCurrentIndex(self.window.source_type.findData("search"))
        self.window.source_value.setText("MrBeast")

        self.window.source_value.returnPressed.emit()
        self.wait_for_ui_actions_idle()

        sources = self.controller.list_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["value"], "MrBeast")
        self.assertEqual(len(self.runner.calls), 1)

    def test_source_max_candidates_default_migrates_from_legacy_50_to_1000(self) -> None:
        self.repo.set_preference(self.controller.LAST_MAX_CANDIDATES_KEY, "50")

        self.window.reset_source_form()

        self.assertEqual(self.controller.get_last_max_candidates(), 1000)
        self.assertEqual(self.window.source_max_candidates.value(), 1000)

    def test_saving_inactive_source_does_not_start_automatic_run(self) -> None:
        self.window.source_type.setCurrentIndex(self.window.source_type.findData("search"))
        self.window.source_value.setText("pausar demo")
        self.window.source_enabled.setChecked(False)

        self.window.save_source()
        self.wait_for_ui_actions_idle()

        self.assertEqual(len(self.controller.list_sources()), 1)
        self.assertEqual(len(self.runner.calls), 0)

    def test_can_delete_multiple_sources_without_deleting_catalog_videos(self) -> None:
        first_id = self.controller.create_source(
            source_type="search",
            label="demo one",
            value="demo one",
            max_candidates_per_run=1000,
            enabled=True,
        )
        second_id = self.controller.create_source(
            source_type="search",
            label="demo two",
            value="demo two",
            max_candidates_per_run=1000,
            enabled=True,
        )
        self.repo.upsert_candidate(
            CandidateVideo(
                video_id="video-1",
                title="Demo video",
                channel="Demo channel",
                channel_id="chan1",
                duration_seconds=60,
                thumbnail_url="",
                source_id=first_id,
                discovered_at=to_iso(),
            )
        )
        self.repo.store_inspection_result(
            "video-1",
            audio_languages=["en", "es-419"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=100,
        )
        self.window.refresh_sources()

        selection_model = self.window.sources_table.selectionModel()
        selection_model.select(self.window.sources_table.model().index(0, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        selection_model.select(self.window.sources_table.model().index(1, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.app.processEvents()

        with patch.object(self.window, "confirm_delete_sources", return_value=False):
            self.window.delete_selected_sources()
            self.wait_for_ui_actions_idle()

        self.assertEqual(self.controller.list_sources(), [])
        catalog = self.controller.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["video_id"], "video-1")

    def test_delete_source_cancel_leaves_source_and_videos_untouched(self) -> None:
        source_id = self.controller.create_source(
            source_type="search",
            label="demo",
            value="demo",
            max_candidates_per_run=1000,
            enabled=True,
        )
        self.repo.upsert_candidate(
            CandidateVideo(
                video_id="video-cancel",
                title="Demo video",
                channel="Demo channel",
                channel_id="chan1",
                duration_seconds=60,
                thumbnail_url="",
                source_id=source_id,
                discovered_at=to_iso(),
            )
        )
        self.repo.store_inspection_result(
            "video-cancel",
            audio_languages=["en", "es-419"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=100,
        )
        self.window.refresh_sources()
        self.window.sources_table.selectRow(0)
        self.app.processEvents()

        with patch.object(self.window, "confirm_delete_sources", return_value=None):
            self.window.delete_selected_sources()

        self.assertEqual(len(self.controller.list_sources()), 1)
        catalog = self.controller.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        self.assertEqual([item["video_id"] for item in catalog], ["video-cancel"])

    def test_delete_source_can_delete_saved_videos_when_confirmed(self) -> None:
        source_id = self.controller.create_source(
            source_type="search",
            label="demo",
            value="demo",
            max_candidates_per_run=1000,
            enabled=True,
        )
        self.repo.upsert_candidate(
            CandidateVideo(
                video_id="video-delete",
                title="Demo video",
                channel="Demo channel",
                channel_id="chan1",
                duration_seconds=60,
                thumbnail_url="",
                source_id=source_id,
                discovered_at=to_iso(),
            )
        )
        self.repo.store_inspection_result(
            "video-delete",
            audio_languages=["en", "es-419"],
            has_dubbing=True,
            published_at="2026-04-20",
            view_count=100,
        )
        self.window.refresh_sources()

        row = next(
            index
            for index, source in enumerate(self.controller.list_sources())
            if int(source["id"]) == int(source_id)
        )
        self.window.sources_table.selectRow(row)
        self.app.processEvents()

        with patch.object(self.window, "confirm_delete_sources", return_value=True):
            self.window.delete_selected_sources()
            self.wait_for_ui_actions_idle()

        self.assertEqual(self.controller.list_sources(), [])
        catalog = self.controller.list_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        self.assertEqual(catalog, [])


if __name__ == "__main__":
    unittest.main()
