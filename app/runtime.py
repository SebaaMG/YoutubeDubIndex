from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root(project_root: Path) -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return project_root


def executable_root(project_root: Path) -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return project_root


def local_appdata_root(app_dir_name: str) -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / app_dir_name
    return Path.home() / "AppData" / "Local" / app_dir_name


def app_root(project_root: Path, app_dir_name: str) -> Path:
    if is_frozen():
        return executable_root(project_root)
    return project_root
