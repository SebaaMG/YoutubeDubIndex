from __future__ import annotations

import argparse
import os
import sys
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
from app.youtube import StartupDiagnostics, YouTubeService  # noqa: E402


class IdleRunner:
    def active_run_id(self) -> int | None:
        return None

    def start_run(self, *args, **kwargs) -> int:
        raise RuntimeError("disabled in UI perf harness")

    def start_metadata_backfill(self, *args, **kwargs) -> None:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
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
        youtube=YouTubeService(settings),
        runner=IdleRunner(),
        diagnostics=StartupDiagnostics(node_ok=True, ytdlp_ok=True, messages=[]),
    )
    window = MainWindow(AppController(services), services)
    window.resize(1680, 980)
    start = time.perf_counter()
    window.switch_page("catalog")
    window.show()
    app.processEvents()
    first_visible_ms = (time.perf_counter() - start) * 1000

    beats: list[float] = []
    last = time.perf_counter()

    def heartbeat() -> None:
        nonlocal last
        now = time.perf_counter()
        beats.append((now - last) * 1000)
        last = now
        if len(beats) >= 120:
            app.quit()

    timer = QTimer()
    timer.setInterval(16)
    timer.timeout.connect(heartbeat)
    timer.start()
    app.exec()
    p99 = sorted(beats)[int(len(beats) * 0.99) - 1] if beats else 0
    print(f"first_visible_ms={first_visible_ms:.1f} heartbeat_p99_ms={p99:.1f} model_rows={window.catalog_model.rowCount()}")
    window.close()


if __name__ == "__main__":
    main()
