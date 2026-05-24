from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.desktop_services import AppController, build_services
from app.ui import launch_app
from app.worker import run_discovery_worker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--worker", choices=["discovery"], default=None)
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)
    if args.worker == "discovery":
        return run_discovery_worker(db_path=Path(args.db) if args.db else None)

    services = build_services()
    controller = AppController(services)
    return launch_app(controller, services)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
