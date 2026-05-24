from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.config import Settings
from app.db import Database
from app.desktop_services import AppController, DesktopServices, build_services
from app.repository import Repository
from app.youtube import StartupDiagnostics


class FakeWorkerClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.notifications: list[tuple[str, dict[str, object]]] = []
        self._active_run_id: int | None = None

    def call(self, command: str, payload: dict[str, object] | None = None, timeout: float | None = None) -> object:
        del timeout
        data = dict(payload or {})
        self.calls.append((command, data))
        if command == "submit_interest":
            return {"seed_id": 42, "source_type": "search", "label": data["raw_value"], "value": data["raw_value"]}
        if command == "run_manual_feed":
            return {"summary": {"inspected": data["candidate_limit"], "verified": 3}}
        if command == "run_source":
            self._active_run_id = 77
            return {"run_id": 77}
        if command == "run_all":
            self._active_run_id = 78
            return {"run_id": 78}
        if command == "metadata_backfill":
            self._active_run_id = 79
            return {"run_id": 79}
        if command == "run_interest_initial_discovery":
            return {"summary": {"related_candidates": data["candidate_limit"]}}
        return {}

    def notify(self, command: str, payload: dict[str, object] | None = None) -> None:
        self.notifications.append((command, dict(payload or {})))

    def active_run_id(self) -> int | None:
        return self._active_run_id


class WorkerArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = Settings(project_root=Path(self.temp_dir.name))
        self.db = Database(self.settings.db_path)
        self.db.initialize()
        self.repo = Repository(self.db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_ui_services_do_not_construct_youtube_or_discovery_loop(self) -> None:
        with patch("app.desktop_services.YouTubeService", side_effect=AssertionError("UI must not import yt_dlp")):
            services = build_services(settings=self.settings, start_worker=False)

        self.assertIsNone(services.youtube)
        self.assertIsNone(services.runner)
        self.assertIsNone(services.discovery_worker)
        self.assertIsNone(services.discovery_loop)

    def test_controller_routes_search_commands_to_worker_client(self) -> None:
        worker = FakeWorkerClient()
        services = DesktopServices(
            settings=self.settings,
            db=self.db,
            repo=self.repo,
            youtube=None,
            runner=None,
            diagnostics=StartupDiagnostics(node_ok=True, ytdlp_ok=True, messages=[]),
            worker_client=worker,
        )
        controller = AppController(services)

        self.assertEqual(controller.submit_interest("internet mystery")["seed_id"], 42)
        self.assertEqual(controller.run_manual_feed_expansion(candidate_limit=200)["verified"], 3)
        self.assertEqual(controller.run_interest_initial_discovery(42, candidate_limit=150)["related_candidates"], 150)
        self.assertEqual(controller.run_source(5), 77)
        self.assertEqual(controller.run_all(), 78)
        self.assertEqual(controller.start_metadata_backfill(limit=25), 79)
        controller.pause_background(seconds=0.5)

        self.assertEqual(
            worker.calls,
            [
                ("submit_interest", {"raw_value": "internet mystery"}),
                ("run_manual_feed", {"candidate_limit": 200}),
                ("run_interest_initial_discovery", {"seed_id": 42, "candidate_limit": 150}),
                ("run_source", {"source_id": 5}),
                ("run_all", {}),
                ("metadata_backfill", {"limit": 25}),
            ],
        )
        self.assertEqual(worker.notifications, [("pause_background", {"seconds": 0.5})])
        self.assertEqual(controller.active_run_id(), 79)

    def test_controller_persists_and_routes_automatic_search_toggle(self) -> None:
        worker = FakeWorkerClient()
        services = DesktopServices(
            settings=self.settings,
            db=self.db,
            repo=self.repo,
            youtube=None,
            runner=None,
            diagnostics=StartupDiagnostics(node_ok=True, ytdlp_ok=True, messages=[]),
            worker_client=worker,
        )
        controller = AppController(services)

        self.assertTrue(controller.automatic_discovery_enabled())

        controller.set_automatic_discovery_enabled(False)
        self.assertFalse(controller.automatic_discovery_enabled())
        controller.set_automatic_discovery_enabled(True)
        self.assertTrue(controller.automatic_discovery_enabled())

        self.assertEqual(
            worker.notifications[-2:],
            [
                ("set_background_enabled", {"enabled": False}),
                ("set_background_enabled", {"enabled": True}),
            ],
        )

    def test_automatic_discovery_interval_defaults_to_five_minutes(self) -> None:
        self.assertEqual(self.settings.discovery_loop_interval_seconds, 300)

    def test_ui_read_connection_is_query_only_and_has_short_busy_timeout(self) -> None:
        with self.db.connect(profile="ui_read") as conn:
            timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
            query_only = int(conn.execute("PRAGMA query_only").fetchone()[0])

            with self.assertRaises(Exception):
                conn.execute("CREATE TABLE forbidden_write(id INTEGER)")

        self.assertLessEqual(timeout, 1000)
        self.assertEqual(query_only, 1)

    def test_worker_write_connection_uses_normal_sync_and_disables_autocheckpoint(self) -> None:
        with self.db.connect(profile="worker_write") as conn:
            synchronous = int(conn.execute("PRAGMA synchronous").fetchone()[0])
            autocheckpoint = int(conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0])

        self.assertEqual(synchronous, 1)
        self.assertEqual(autocheckpoint, 0)

    def test_catalog_and_summary_reads_use_ui_read_profile(self) -> None:
        class RecordingDatabase(Database):
            def __init__(self, path: Path) -> None:
                super().__init__(path)
                self.profiles: list[str] = []

            def connect(self, *, profile: str = "default"):  # type: ignore[override]
                self.profiles.append(profile)
                return super().connect(profile=profile)

        db = RecordingDatabase(Path(self.temp_dir.name) / "profiles.db")
        db.initialize()
        repo = Repository(db)
        db.profiles.clear()

        repo.dashboard_stats()
        repo.list_sources()
        repo.list_runs(limit=5)
        repo.count_catalog(
            lang=None,
            source_id=None,
            channel=None,
            query=None,
            only_dubbed=True,
        )
        repo.list_catalog_filters()

        self.assertNotIn("default", db.profiles)
        self.assertGreaterEqual(db.profiles.count("ui_read"), 5)


if __name__ == "__main__":
    unittest.main()
