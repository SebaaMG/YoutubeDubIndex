from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any, Callable, TextIO

from .config import Settings, get_settings
from .desktop_services import AppController, DesktopServices, build_worker_services


EmitFn = Callable[[dict[str, Any]], None]


class WorkerOutputClosed(RuntimeError):
    pass


class DiscoveryWorkerJsonServer:
    def __init__(
        self,
        *,
        controller: AppController,
        services: DesktopServices,
        emit: EmitFn | None = None,
        output_stream: TextIO | None = None,
    ) -> None:
        self.controller = controller
        self.services = services
        self._write_lock = threading.Lock()
        self._emit = emit
        self._output_stream = output_stream
        runner = getattr(services, "runner", None)
        if runner is not None and hasattr(runner, "set_event_callback"):
            runner.set_event_callback(self.emit_event)

    def emit_event(self, payload: dict[str, Any]) -> None:
        if self._emit is not None:
            self._emit(dict(payload))
            return
        self.write_message(payload)

    def write_message(self, payload: dict[str, Any]) -> None:
        output_stream = self._output_stream or sys.stdout
        if output_stream is None:
            raise WorkerOutputClosed("worker stdout is not available")
        with self._write_lock:
            try:
                output_stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
                output_stream.flush()
            except (BrokenPipeError, OSError, ValueError) as exc:
                raise WorkerOutputClosed("worker stdout was closed") from exc

    def handle_command(self, message: dict[str, Any]) -> dict[str, Any]:
        command = str(message.get("command") or "")
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        if command == "submit_interest":
            return self.controller.submit_interest(str(payload.get("raw_value") or ""))
        if command == "run_interest_initial_discovery":
            self._pause_background(0.5)
            summary = self.controller.run_interest_initial_discovery(
                int(payload.get("seed_id") or 0),
                candidate_limit=int(payload.get("candidate_limit") or 150),
            )
            self._idle_checkpoint()
            self.emit_event({"event": "catalog_changed"})
            return {"summary": summary}
        if command == "run_manual_feed":
            self._pause_background(0.5)
            summary = self.controller.run_manual_feed_expansion(
                candidate_limit=int(payload.get("candidate_limit") or 200)
            )
            self._idle_checkpoint()
            self.emit_event({"event": "catalog_changed"})
            return {"summary": summary}
        if command == "run_discovery_once":
            summary = self.controller.run_discovery_once(
                max_seed_discoveries=payload.get("max_seed_discoveries"),
                max_candidate_inspections=payload.get("max_candidate_inspections"),
            )
            self._idle_checkpoint()
            self.emit_event({"event": "catalog_changed"})
            return {"summary": summary}
        if command == "run_source":
            run_id = self.controller.run_source(int(payload.get("source_id") or 0))
            self.emit_event({"event": "run_started", "run_id": run_id})
            return {"run_id": run_id}
        if command == "run_all":
            run_id = self.controller.run_all()
            self.emit_event({"event": "run_started", "run_id": run_id})
            return {"run_id": run_id}
        if command == "metadata_backfill":
            raw_limit = payload.get("limit")
            run_id = self.controller.start_metadata_backfill(
                limit=int(raw_limit) if raw_limit is not None else None
            )
            if run_id is not None:
                self.emit_event({"event": "run_started", "run_id": run_id})
            return {"run_id": run_id}
        if command == "pause_background":
            self._pause_background(float(payload.get("seconds") or 0.5))
            return {}
        if command == "resume_background":
            loop = self.services.discovery_loop
            if loop is not None and hasattr(loop, "resume"):
                loop.resume()
            return {}
        if command == "set_background_enabled":
            enabled = bool(payload.get("enabled"))
            loop = self.services.discovery_loop
            if loop is not None and hasattr(loop, "set_enabled"):
                loop.set_enabled(enabled)
            return {"enabled": enabled}
        if command == "active_run_id":
            active_run_id = self.controller.active_run_id()
            return {"active_run_id": active_run_id}
        if command == "shutdown":
            if self.services.discovery_loop is not None:
                self.services.discovery_loop.stop()
            return {"keep_running": False}
        raise ValueError(f"Comando de worker no soportado: {command}")

    def _pause_background(self, seconds: float) -> None:
        loop = self.services.discovery_loop
        if loop is not None and hasattr(loop, "pause_for"):
            loop.pause_for(seconds)

    def _idle_checkpoint(self) -> None:
        db = getattr(self.services, "db", None)
        if db is not None and hasattr(db, "checkpoint"):
            try:
                db.checkpoint(mode="PASSIVE")
            except Exception:
                pass

    def serve(self, input_stream: TextIO | None = None) -> None:
        stream = input_stream or sys.stdin
        if stream is None:
            return
        try:
            self.emit_event({"event": "ready"})
        except WorkerOutputClosed:
            return
        keep_running = True
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("Mensaje invalido")
                request_id = message.get("id")
                result = self.handle_command(message)
                keep_running = bool(result.pop("keep_running", True))
                if request_id is not None:
                    self.write_message({"id": request_id, "ok": True, "result": result})
            except WorkerOutputClosed:
                break
            except Exception as exc:
                request_id = None
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        request_id = parsed.get("id")
                except Exception:
                    pass
                error_payload = {"ok": False, "error": str(exc)[:500]}
                if request_id is not None:
                    error_payload["id"] = request_id
                else:
                    error_payload["event"] = "error"
                    error_payload["message"] = str(exc)[:500]
                try:
                    self.write_message(error_payload)
                except WorkerOutputClosed:
                    break
            if not keep_running:
                break


def run_discovery_worker(*, db_path: Path | None = None, settings: Settings | None = None) -> int:
    services = build_worker_services(settings=settings or get_settings(), db_path=db_path)
    controller = AppController(services)
    DiscoveryWorkerJsonServer(controller=controller, services=services).serve()
    return 0
