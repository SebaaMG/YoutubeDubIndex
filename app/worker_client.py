from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from .config import Settings
from . import runtime


class SearchWorkerProcessClient:
    def __init__(
        self,
        *,
        settings: Settings,
        db_path: Path,
        autostart: bool = True,
    ) -> None:
        self.settings = settings
        self.db_path = Path(db_path)
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._response_lock = threading.Lock()
        self._responses: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._next_id = 0
        self._active_run_id: int | None = None
        self._last_error: str | None = None
        if autostart:
            self.start()

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        args = self._worker_args()
        env = None
        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            args,
            cwd=str(self.settings.project_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=creationflags,
        )
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True, name="search-worker-reader")
        self._reader_thread.start()

    def _worker_args(self) -> list[str]:
        if runtime.is_frozen():
            executable = Path(sys.executable)
            worker_name = f"{executable.stem}Worker{executable.suffix}"
            worker_candidates = [
                executable.parent / "_internal" / worker_name,
                executable.with_name(worker_name),
            ]
            for worker_executable in worker_candidates:
                if worker_executable.exists():
                    return [str(worker_executable), "--worker", "discovery", "--db", str(self.db_path)]
            return [str(executable), "--worker", "discovery", "--db", str(self.db_path)]
        return [
            sys.executable,
            str(self.settings.project_root / "main.py"),
            "--worker",
            "discovery",
            "--db",
            str(self.db_path),
        ]

    def call(
        self,
        command: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        self.start()
        request_id = self._send(command, payload or {}, expect_response=True)
        response_queue = self._responses[request_id]
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError(f"Worker command timed out: {command}") from exc
        finally:
            with self._response_lock:
                self._responses.pop(request_id, None)
        if not response.get("ok", False):
            raise RuntimeError(str(response.get("error") or f"Worker command failed: {command}"))
        return response.get("result")

    def notify(self, command: str, payload: dict[str, Any] | None = None) -> None:
        try:
            self.start()
            self._send(command, payload or {}, expect_response=False)
        except Exception as exc:
            self._last_error = str(exc)

    def _send(self, command: str, payload: dict[str, Any], *, expect_response: bool) -> str:
        process = self._process
        if process is None or process.stdin is None or process.poll() is not None:
            raise RuntimeError("El proceso de busqueda no esta disponible.")
        with self._write_lock:
            self._next_id += 1
            request_id = str(self._next_id)
            if expect_response:
                with self._response_lock:
                    self._responses[request_id] = queue.Queue(maxsize=1)
            line = json.dumps(
                {"id": request_id, "command": command, "payload": payload},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            process.stdin.write(line + "\n")
            process.stdin.flush()
        return request_id

    def _read_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                self.handle_worker_message(message)
        with self._response_lock:
            pending = list(self._responses.values())
        for response_queue in pending:
            response_queue.put({"ok": False, "error": "El proceso de busqueda se cerro inesperadamente."})

    def handle_worker_message(self, message: dict[str, Any]) -> None:
        if "id" in message:
            request_id = str(message["id"])
            with self._response_lock:
                response_queue = self._responses.get(request_id)
            if response_queue is not None:
                response_queue.put(message)
            return

        event = str(message.get("event") or "")
        if event == "run_started":
            run_id = message.get("run_id")
            self._active_run_id = int(run_id) if run_id is not None else None
        elif event == "run_finished":
            run_id = message.get("run_id")
            if run_id is None or self._active_run_id == int(run_id):
                self._active_run_id = None
        elif event == "error":
            self._last_error = str(message.get("message") or "")

    def active_run_id(self) -> int | None:
        return self._active_run_id

    def stop(self, *, wait: bool = False) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        if wait:
            self._stop_process(process)
            return
        threading.Thread(
            target=self._stop_process,
            args=(process,),
            daemon=True,
            name="search-worker-stop",
        ).start()

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        try:
            self._send("shutdown", {}, expect_response=False)
        except Exception as exc:
            self._last_error = str(exc)
        try:
            if process.stdin is not None:
                process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=1.0)
            return
        except Exception:
            pass
        try:
            if process.poll() is None:
                process.terminate()
        except Exception:
            pass
