from __future__ import annotations

import queue
import io
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.worker import DiscoveryWorkerJsonServer
from app.worker_client import SearchWorkerProcessClient


class FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def submit_interest(self, raw_value: str) -> dict[str, object]:
        self.calls.append(("submit_interest", {"raw_value": raw_value}))
        return {"seed_id": 10}

    def run_interest_initial_discovery(self, seed_id: int, *, candidate_limit: int) -> dict[str, int]:
        self.calls.append(("run_interest_initial_discovery", {"seed_id": seed_id, "candidate_limit": candidate_limit}))
        return {"related_candidates": candidate_limit}

    def run_manual_feed_expansion(self, *, candidate_limit: int) -> dict[str, int]:
        self.calls.append(("run_manual_feed_expansion", {"candidate_limit": candidate_limit}))
        return {"verified": 4}

    def run_source(self, source_id: int) -> int:
        self.calls.append(("run_source", {"source_id": source_id}))
        return 55

    def run_all(self) -> int:
        self.calls.append(("run_all", {}))
        return 56

    def start_metadata_backfill(self, *, limit: int | None = None) -> int | None:
        self.calls.append(("start_metadata_backfill", {"limit": limit}))
        return 57


class FakeDiscoveryLoop:
    def __init__(self) -> None:
        self.pauses: list[float] = []
        self.resumed = False
        self.stopped = False
        self.enabled_values: list[bool] = []

    def pause_for(self, seconds: float) -> None:
        self.pauses.append(seconds)

    def resume(self) -> None:
        self.resumed = True

    def stop(self) -> None:
        self.stopped = True

    def set_enabled(self, enabled: bool) -> None:
        self.enabled_values.append(enabled)


class FakeDatabase:
    def __init__(self) -> None:
        self.checkpoints: list[str] = []

    def checkpoint(self, *, mode: str = "PASSIVE") -> None:
        self.checkpoints.append(mode)


class WorkerIpcTests(unittest.TestCase):
    def test_server_routes_commands_and_pauses_background_work(self) -> None:
        controller = FakeController()
        loop = FakeDiscoveryLoop()
        db = FakeDatabase()
        emitted: list[dict[str, object]] = []
        server = DiscoveryWorkerJsonServer(
            controller=controller,
            services=SimpleNamespace(discovery_loop=loop, db=db, runner=SimpleNamespace(set_event_callback=lambda cb: None)),
            emit=emitted.append,
        )

        self.assertEqual(server.handle_command({"command": "submit_interest", "payload": {"raw_value": "demo"}}), {"seed_id": 10})
        self.assertEqual(
            server.handle_command({"command": "run_interest_initial_discovery", "payload": {"seed_id": 10, "candidate_limit": 150}}),
            {"summary": {"related_candidates": 150}},
        )
        self.assertEqual(
            server.handle_command({"command": "run_manual_feed", "payload": {"candidate_limit": 200}}),
            {"summary": {"verified": 4}},
        )
        self.assertEqual(server.handle_command({"command": "run_source", "payload": {"source_id": 5}}), {"run_id": 55})
        self.assertEqual(server.handle_command({"command": "run_all", "payload": {}}), {"run_id": 56})
        self.assertEqual(server.handle_command({"command": "metadata_backfill", "payload": {"limit": 25}}), {"run_id": 57})
        self.assertEqual(server.handle_command({"command": "pause_background", "payload": {"seconds": 0.5}}), {})
        self.assertEqual(server.handle_command({"command": "resume_background", "payload": {}}), {})
        self.assertEqual(server.handle_command({"command": "set_background_enabled", "payload": {"enabled": False}}), {"enabled": False})
        self.assertEqual(server.handle_command({"command": "set_background_enabled", "payload": {"enabled": True}}), {"enabled": True})
        self.assertFalse(server.handle_command({"command": "shutdown", "payload": {}})["keep_running"])

        self.assertEqual(loop.pauses, [0.5, 0.5, 0.5])
        self.assertTrue(loop.resumed)
        self.assertEqual(loop.enabled_values, [False, True])
        self.assertTrue(loop.stopped)
        self.assertIn({"event": "run_started", "run_id": 55}, emitted)
        self.assertIn("PASSIVE", db.checkpoints)

    def test_client_tracks_active_run_from_worker_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(project_root=Path(temp_dir))
            client = SearchWorkerProcessClient(settings=settings, db_path=settings.db_path, autostart=False)

            client.handle_worker_message({"event": "run_started", "run_id": 123})
            self.assertEqual(client.active_run_id(), 123)
            client.handle_worker_message({"event": "run_finished", "run_id": 122})
            self.assertEqual(client.active_run_id(), 123)
            client.handle_worker_message({"event": "run_finished", "run_id": 123})
            self.assertIsNone(client.active_run_id())

    def test_client_non_waiting_stop_returns_without_blocking_on_busy_ipc(self) -> None:
        class FakeProcess:
            stdin = object()

            def poll(self) -> None:
                return None

        class SlowStopClient(SearchWorkerProcessClient):
            def start(self) -> None:
                return

            def _send(self, command: str, payload: dict[str, object], *, expect_response: bool) -> str:  # type: ignore[override]
                time.sleep(0.5)
                return "slow"

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(project_root=Path(temp_dir))
            client = SlowStopClient(settings=settings, db_path=settings.db_path, autostart=False)
            client._process = FakeProcess()  # type: ignore[assignment]

            started = time.perf_counter()
            client.stop(wait=False)
            elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.1)

    def test_server_exits_cleanly_when_stdout_is_unavailable(self) -> None:
        class BrokenOutput:
            def write(self, _text: str) -> int:
                raise OSError(22, "Invalid argument")

            def flush(self) -> None:
                raise OSError(22, "Invalid argument")

        controller = FakeController()
        server = DiscoveryWorkerJsonServer(
            controller=controller,
            services=SimpleNamespace(discovery_loop=None, db=None, runner=SimpleNamespace(set_event_callback=lambda cb: None)),
            output_stream=BrokenOutput(),  # type: ignore[arg-type]
        )

        server.serve(io.StringIO(""))

    def test_frozen_client_prefers_sibling_console_worker_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gui_exe = root / "YouTubeDubIndexer.exe"
            worker_exe = root / "_internal" / "YouTubeDubIndexerWorker.exe"
            worker_exe.parent.mkdir()
            gui_exe.write_text("", encoding="utf-8")
            worker_exe.write_text("", encoding="utf-8")
            settings = Settings(project_root=root)
            client = SearchWorkerProcessClient(settings=settings, db_path=settings.db_path, autostart=False)

            import app.worker_client as worker_client_module

            original_is_frozen = worker_client_module.runtime.is_frozen
            original_executable = worker_client_module.sys.executable
            try:
                worker_client_module.runtime.is_frozen = lambda: True  # type: ignore[assignment]
                worker_client_module.sys.executable = str(gui_exe)

                args = client._worker_args()
            finally:
                worker_client_module.runtime.is_frozen = original_is_frozen  # type: ignore[assignment]
                worker_client_module.sys.executable = original_executable

            self.assertEqual(Path(args[0]), worker_exe)
            self.assertEqual(args[1:3], ["--worker", "discovery"])

    def test_frozen_client_falls_back_to_sibling_worker_for_old_builds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gui_exe = root / "YouTubeDubIndexer.exe"
            worker_exe = root / "YouTubeDubIndexerWorker.exe"
            gui_exe.write_text("", encoding="utf-8")
            worker_exe.write_text("", encoding="utf-8")
            settings = Settings(project_root=root)
            client = SearchWorkerProcessClient(settings=settings, db_path=settings.db_path, autostart=False)

            import app.worker_client as worker_client_module

            original_is_frozen = worker_client_module.runtime.is_frozen
            original_executable = worker_client_module.sys.executable
            try:
                worker_client_module.runtime.is_frozen = lambda: True  # type: ignore[assignment]
                worker_client_module.sys.executable = str(gui_exe)

                args = client._worker_args()
            finally:
                worker_client_module.runtime.is_frozen = original_is_frozen  # type: ignore[assignment]
                worker_client_module.sys.executable = original_executable

            self.assertEqual(Path(args[0]), worker_exe)
            self.assertEqual(args[1:3], ["--worker", "discovery"])


if __name__ == "__main__":
    unittest.main()
