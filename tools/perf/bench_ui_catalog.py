from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.desktop_services import AppController, DesktopServices  # noqa: E402
from app.repository import Repository  # noqa: E402
from app.ui import APP_STYLE, MainWindow  # noqa: E402
from app.youtube import StartupDiagnostics  # noqa: E402


class IdleRunner:
    def active_run_id(self) -> int | None:
        return None

    def start_run(self, *args, **kwargs) -> int:
        raise RuntimeError("disabled in UI perf harness")

    def start_metadata_backfill(self, *args, **kwargs) -> None:
        return None


class NullThumbnailService:
    def __init__(self) -> None:
        self._dropped = 0

    def request(self, _url: str, _target_size: QSize, _callback) -> None:
        return None

    def prune_pending(self, allowed_keys: set[tuple[str, int, int]]) -> None:
        return None

    def active_request_count(self) -> int:
        return 0

    def pending_request_count(self) -> int:
        return 0

    def dropped_pending_count(self) -> int:
        return self._dropped

    def shutdown(self) -> None:
        return None


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * ratio) - 1))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--scroll", action="store_true", help="continuously scroll the Discover list during the run")
    parser.add_argument("--disable-thumbnails", action="store_true", help="replace thumbnail loading with a no-op service")
    parser.add_argument("--duration", type=float, default=2.0, help="seconds to sample the event loop")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(APP_STYLE)
    settings = Settings(project_root=ROOT, db_filename=args.db.name)
    db = Database(args.db)
    repo = Repository(db)
    services = DesktopServices(
        settings=settings,
        db=db,
        repo=repo,
        youtube=None,
        runner=IdleRunner(),
        diagnostics=StartupDiagnostics(node_ok=True, ytdlp_ok=True, messages=[]),
    )
    window = MainWindow(AppController(services), services)
    if args.disable_thumbnails:
        window.thumbnail_service.shutdown()
        window.thumbnail_service = NullThumbnailService()  # type: ignore[assignment]
    window.resize(1680, 980)
    start = time.perf_counter()
    window.switch_page("catalog")
    window.show()
    app.processEvents()
    first_visible_ms = (time.perf_counter() - start) * 1000

    beats: list[float] = []
    last = time.perf_counter()
    end_at = last + max(0.1, float(args.duration))
    scroll_direction = 1

    def heartbeat() -> None:
        nonlocal last, scroll_direction
        now = time.perf_counter()
        beats.append((now - last) * 1000)
        last = now
        if args.scroll:
            bar = window.catalog_view.verticalScrollBar()
            maximum = bar.maximum()
            if maximum > 0:
                next_value = bar.value() + scroll_direction * max(160, window.catalog_view.viewport().height() // 2)
                if next_value >= maximum:
                    next_value = maximum
                    scroll_direction = -1
                elif next_value <= 0:
                    next_value = 0
                    scroll_direction = 1
                bar.setValue(next_value)
        if now >= end_at:
            app.quit()

    timer = QTimer()
    timer.setInterval(16)
    timer.timeout.connect(heartbeat)
    timer.start()
    app.exec()
    thumb_service = window.thumbnail_service
    metrics = {
        "first_visible_ms": round(first_visible_ms, 1),
        "heartbeat_p95_ms": round(percentile(beats, 0.95), 1),
        "heartbeat_p99_ms": round(percentile(beats, 0.99), 1),
        "max_gap_ms": round(max(beats) if beats else 0.0, 1),
        "rows_loaded": window.catalog_model.rowCount(),
        "thumb_active": int(getattr(thumb_service, "active_request_count", lambda: 0)()),
        "thumb_pending": int(getattr(thumb_service, "pending_request_count", lambda: 0)()),
        "thumb_dropped": int(getattr(thumb_service, "dropped_pending_count", lambda: 0)()),
        "samples": len(beats),
    }
    if args.json:
        print(json.dumps(metrics, sort_keys=True))
    else:
        print(" ".join(f"{key}={value}" for key, value in metrics.items()))
    window.close()


if __name__ == "__main__":
    main()
