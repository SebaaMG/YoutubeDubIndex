from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
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


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * ratio) - 1))]


def fake_search_load(db_path: Path, stop: threading.Event | None = None, *, duration: float | None = None) -> None:
    deadline = time.perf_counter() + duration if duration is not None else None
    conn = sqlite3.connect(db_path, timeout=1.0)
    conn.execute("PRAGMA busy_timeout=1000")
    try:
        value = 0.0
        while True:
            if stop is not None and stop.is_set():
                return
            if deadline is not None and time.perf_counter() >= deadline:
                return
            for index in range(40_000):
                value += math.sqrt((index % 97) + 1)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("SELECT COUNT(*) FROM videos").fetchone()
                conn.rollback()
            except sqlite3.Error:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
    finally:
        conn.close()


def start_process_load(db_path: Path, duration: float) -> subprocess.Popen[str]:
    code = (
        "from pathlib import Path; "
        "from tools.perf.bench_ui_under_search import fake_search_load; "
        f"fake_search_load(Path({str(db_path)!r}), duration={float(duration)!r})"
    )
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=creationflags,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--mode", choices=["thread", "process"], default="process")
    parser.add_argument("--scroll", action="store_true")
    parser.add_argument("--clicks", action="store_true")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    stop_load = threading.Event()
    process: subprocess.Popen[str] | None = None
    load_thread: threading.Thread | None = None
    if args.mode == "thread":
        load_thread = threading.Thread(target=fake_search_load, args=(args.db, stop_load), name="fake-search-load")
        load_thread.start()
    else:
        process = start_process_load(args.db, max(0.2, float(args.duration)))

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
        runner=IdleRunner(),  # type: ignore[arg-type]
        diagnostics=StartupDiagnostics(node_ok=True, ytdlp_ok=True, messages=[]),
    )
    window = MainWindow(AppController(services), services)
    window.resize(1680, 980)
    window.switch_page("catalog")
    window.show()
    app.processEvents()

    beats: list[float] = []
    click_times: list[float] = []
    last = time.perf_counter()
    end_at = last + max(0.2, float(args.duration))
    scroll_direction = 1
    ticks = 0

    def heartbeat() -> None:
        nonlocal last, scroll_direction, ticks
        now = time.perf_counter()
        beats.append((now - last) * 1000)
        last = now
        ticks += 1
        if args.scroll:
            bar = window.catalog_view.verticalScrollBar()
            maximum = bar.maximum()
            if maximum > 0:
                step = max(180, window.catalog_view.viewport().height() // 2)
                next_value = bar.value() + scroll_direction * step
                if next_value >= maximum:
                    next_value = maximum
                    scroll_direction = -1
                elif next_value <= 0:
                    next_value = 0
                    scroll_direction = 1
                bar.setValue(next_value)
        if args.clicks and ticks % 18 == 0:
            started = time.perf_counter()
            window.catalog_filters_toggle.click()
            click_times.append((time.perf_counter() - started) * 1000)
        if now >= end_at:
            app.quit()

    timer = QTimer()
    timer.setInterval(16)
    timer.timeout.connect(heartbeat)
    timer.start()
    app.exec()
    stop_load.set()
    if load_thread is not None:
        load_thread.join(timeout=2)
    if process is not None:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.terminate()

    metrics = {
        "mode": args.mode,
        "heartbeat_p95_ms": round(percentile(beats, 0.95), 1),
        "heartbeat_p99_ms": round(percentile(beats, 0.99), 1),
        "max_gap_ms": round(max(beats) if beats else 0.0, 1),
        "button_p95_ms": round(percentile(click_times, 0.95), 1),
        "button_max_ms": round(max(click_times) if click_times else 0.0, 1),
        "rows_loaded": window.catalog_model.rowCount(),
        "samples": len(beats),
    }
    print(json.dumps(metrics, sort_keys=True) if args.json else " ".join(f"{k}={v}" for k, v in metrics.items()))
    window.close()
    for attr in (
        "_catalog_filter_threads",
        "_catalog_page_threads",
        "_summary_refresh_threads",
        "_catalog_count_threads",
        "_active_run_snapshot_threads",
        "_ui_action_threads",
    ):
        for thread in getattr(window, attr, []):
            if thread.is_alive():
                thread.join(timeout=0.5)


if __name__ == "__main__":
    main()
