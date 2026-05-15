from __future__ import annotations

import sys

from app.desktop_services import AppController, build_services
from app.ui import launch_app


def main() -> int:
    services = build_services()
    controller = AppController(services)
    return launch_app(controller, services)


if __name__ == "__main__":
    raise SystemExit(main())
