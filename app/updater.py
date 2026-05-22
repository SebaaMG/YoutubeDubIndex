from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urljoin
from typing import Any

from . import runtime
from .config import Settings


CHANNEL_ENV_VAR = "YOUTUBE_INDEX_UPDATE_MANIFEST_URL"
CHANNEL_FILE_NAME = "update_channel.json"
UPDATE_STATE_FILE_NAME = "update_state.json"
DEFAULT_TIMEOUT_SECONDS = 45


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateAsset:
    url: str
    sha256: str
    file_name: str
    size: int | None = None


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    notes: str
    app: UpdateAsset
    database: UpdateAsset | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class DownloadedUpdate:
    manifest: UpdateManifest
    update_dir: Path
    app_zip_path: Path
    database_path: Path | None


class UpdateManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def update_state_path(self) -> Path:
        return self.settings.data_dir / UPDATE_STATE_FILE_NAME

    def channel_file_paths(self) -> list[Path]:
        return [
            self.settings.executable_root / CHANNEL_FILE_NAME,
            self.settings.data_dir / CHANNEL_FILE_NAME,
        ]

    def resolve_manifest_url(self) -> str:
        env_url = os.environ.get(CHANNEL_ENV_VAR, "").strip()
        if env_url:
            return env_url

        configured_url = str(getattr(self.settings, "update_manifest_url", "") or "").strip()
        if configured_url:
            return configured_url

        for path in self.channel_file_paths():
            manifest_url = self._read_channel_file(path)
            if manifest_url:
                return manifest_url

        return ""

    def check_for_update(self, manifest_url: str | None = None) -> dict[str, Any]:
        resolved_url = (manifest_url or self.resolve_manifest_url()).strip()
        if not resolved_url:
            return {
                "configured": False,
                "update_available": False,
                "current_version": self.current_version(),
                "message": "No hay canal de actualizacion configurado.",
            }

        manifest = self.fetch_manifest(resolved_url)
        current_version = self.current_version()
        update_available = compare_versions(manifest.version, current_version) > 0
        return {
            "configured": True,
            "update_available": update_available,
            "current_version": current_version,
            "version": manifest.version,
            "notes": manifest.notes,
            "manifest": manifest,
            "message": "Actualizacion disponible." if update_available else "Ya tienes la version mas reciente.",
        }

    def fetch_manifest(self, manifest_url: str) -> UpdateManifest:
        request = urllib.request.Request(
            manifest_url,
            headers={"User-Agent": "YoutubeIndexUpdater/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                payload = response.read(2_000_000)
        except Exception as exc:  # pragma: no cover - urllib wraps platform-specific errors
            raise UpdateError(f"No se pudo leer el manifest de actualizacion: {exc}") from exc

        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception as exc:
            raise UpdateError("El manifest de actualizacion no es JSON valido.") from exc

        if not isinstance(data, dict):
            raise UpdateError("El manifest de actualizacion debe ser un objeto JSON.")

        return parse_manifest(data, base_url=manifest_url)

    def download_update(self, manifest: UpdateManifest) -> DownloadedUpdate:
        safe_version = re.sub(r"[^A-Za-z0-9._-]+", "-", manifest.version).strip("-") or "latest"
        update_dir = self.settings.data_dir / "updates" / safe_version
        update_dir.mkdir(parents=True, exist_ok=True)

        app_zip_path = update_dir / manifest.app.file_name
        self._download_asset(manifest.app, app_zip_path)

        database_path: Path | None = None
        if manifest.database is not None:
            database_path = update_dir / manifest.database.file_name
            self._download_asset(manifest.database, database_path)

        return DownloadedUpdate(
            manifest=manifest,
            update_dir=update_dir,
            app_zip_path=app_zip_path,
            database_path=database_path,
        )

    def launch_update_and_restart(self, downloaded: DownloadedUpdate) -> None:
        if not runtime.is_frozen():
            raise UpdateError("La actualizacion automatica solo esta disponible desde el .exe empaquetado.")

        script_path = Path(tempfile.gettempdir()) / (
            f"youtubeindex-update-{os.getpid()}-{int(datetime.now(timezone.utc).timestamp())}.ps1"
        )
        script_path.write_text(self._build_update_script(downloaded), encoding="utf-8")

        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        try:
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                cwd=str(self.settings.executable_root),
                creationflags=flags,
            )
        except Exception as exc:
            raise UpdateError(f"No se pudo lanzar el instalador de actualizacion: {exc}") from exc

    def current_version(self) -> str:
        state = self._read_update_state()
        state_version = str(state.get("last_version") or "").strip()
        app_version = str(getattr(self.settings, "app_version", "") or "").strip()
        if state_version and compare_versions(state_version, app_version) > 0:
            return state_version
        return app_version or "0"

    def _read_update_state(self) -> dict[str, Any]:
        if not self.update_state_path.exists():
            return {}
        try:
            data = json.loads(self.update_state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _read_channel_file(path: Path) -> str:
        if not path.exists():
            return ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        if not isinstance(data, dict):
            return ""
        return str(data.get("manifest_url") or "").strip()

    @staticmethod
    def _download_asset(asset: UpdateAsset, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = destination.with_name(destination.name + ".download")
        if tmp_path.exists():
            tmp_path.unlink()

        request = urllib.request.Request(asset.url, headers={"User-Agent": "YoutubeIndexUpdater/1.0"})
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                with tmp_path.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
        except Exception as exc:  # pragma: no cover - network errors vary by platform
            if tmp_path.exists():
                tmp_path.unlink()
            raise UpdateError(f"No se pudo descargar {asset.file_name}: {exc}") from exc

        actual_hash = digest.hexdigest().lower()
        expected_hash = asset.sha256.lower()
        if actual_hash != expected_hash:
            tmp_path.unlink(missing_ok=True)
            raise UpdateError(
                f"Hash invalido para {asset.file_name}: esperado {expected_hash}, recibido {actual_hash}."
            )

        tmp_path.replace(destination)

    def _build_update_script(self, downloaded: DownloadedUpdate) -> str:
        app_root = self.settings.executable_root
        backup_root = app_root.with_name(
            f"{app_root.name}.backup-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )
        extract_root = self.settings.data_dir / "updates" / "_extract"
        db_asset = downloaded.database_path or Path("")
        exe_name = Path(sys.executable).name
        if not exe_name.lower().endswith(".exe"):
            exe_name = "YouTubeDubIndexer.exe"

        return f"""$ErrorActionPreference = "Stop"
$appRoot = {ps_quote(str(app_root))}
$backupRoot = {ps_quote(str(backup_root))}
$extractRoot = {ps_quote(str(extract_root))}
$appZip = {ps_quote(str(downloaded.app_zip_path))}
$dbAsset = {ps_quote(str(db_asset))}
$exeName = {ps_quote(exe_name)}
$currentPid = {os.getpid()}
$updateVersion = {ps_quote(downloaded.manifest.version)}
$logPath = Join-Path ([System.IO.Path]::GetTempPath()) "youtubeindex-update.log"

function Log($message) {{
    Add-Content -LiteralPath $logPath -Value ("[{0}] {1}" -f (Get-Date).ToString("o"), $message)
}}

try {{
    Log "Waiting for app process $currentPid"
    try {{ Wait-Process -Id $currentPid -Timeout 90 }} catch {{ Start-Sleep -Seconds 3 }}

    if (Test-Path -LiteralPath $extractRoot) {{
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }}
    New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
    Expand-Archive -LiteralPath $appZip -DestinationPath $extractRoot -Force

    $newRoot = Join-Path $extractRoot "YouTubeDubIndexer"
    if (-not (Test-Path -LiteralPath (Join-Path $newRoot $exeName))) {{
        $newRoot = Get-ChildItem -LiteralPath $extractRoot -Directory |
            Where-Object {{ Test-Path -LiteralPath (Join-Path $_.FullName $exeName) }} |
            Select-Object -First 1 -ExpandProperty FullName
    }}
    if (-not $newRoot -or -not (Test-Path -LiteralPath (Join-Path $newRoot $exeName))) {{
        throw "El zip de actualizacion no contiene $exeName."
    }}

    if (Test-Path -LiteralPath $backupRoot) {{
        Remove-Item -LiteralPath $backupRoot -Recurse -Force
    }}
    Move-Item -LiteralPath $appRoot -Destination $backupRoot
    Move-Item -LiteralPath $newRoot -Destination $appRoot

    $oldData = Join-Path $backupRoot "data"
    $newData = Join-Path $appRoot "data"
    if (Test-Path -LiteralPath $oldData) {{
        if (Test-Path -LiteralPath $newData) {{
            Remove-Item -LiteralPath $newData -Recurse -Force
        }}
        Copy-Item -LiteralPath $oldData -Destination $newData -Recurse -Force
    }} else {{
        New-Item -ItemType Directory -Force -Path $newData | Out-Null
    }}

    if ($dbAsset -and (Test-Path -LiteralPath $dbAsset)) {{
        Copy-Item -LiteralPath $dbAsset -Destination (Join-Path $newData "dub_index_desktop.db") -Force
    }}

    $state = [ordered]@{{
        last_version = $updateVersion
        updated_at = (Get-Date).ToString("o")
    }} | ConvertTo-Json
    Set-Content -LiteralPath (Join-Path $newData "update_state.json") -Value $state -Encoding UTF8

    Start-Process -FilePath (Join-Path $appRoot $exeName) -WorkingDirectory $appRoot
    Start-Sleep -Seconds 8
    if (Test-Path -LiteralPath $extractRoot) {{
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }}
    Log "Update completed"
}} catch {{
    Log ("Update failed: " + $_.Exception.Message)
    if ((-not (Test-Path -LiteralPath $appRoot)) -and (Test-Path -LiteralPath $backupRoot)) {{
        Move-Item -LiteralPath $backupRoot -Destination $appRoot
    }}
    $fallbackExe = Join-Path $appRoot $exeName
    if (Test-Path -LiteralPath $fallbackExe) {{
        Start-Process -FilePath $fallbackExe -WorkingDirectory $appRoot
    }}
    exit 1
}}
"""


def parse_manifest(data: dict[str, Any], *, base_url: str) -> UpdateManifest:
    version = str(data.get("version") or "").strip()
    if not version:
        raise UpdateError("El manifest no tiene version.")

    app_data = data.get("app")
    if not isinstance(app_data, dict):
        raise UpdateError("El manifest no tiene asset de app.")

    database_data = data.get("database")
    database = parse_asset(database_data, base_url=base_url, default_file_name="dub_index_desktop.db") if isinstance(database_data, dict) else None
    return UpdateManifest(
        version=version,
        notes=str(data.get("notes") or "").strip(),
        app=parse_asset(app_data, base_url=base_url, default_file_name="YouTubeDubIndexer-portable.zip"),
        database=database,
        raw=data,
    )


def parse_asset(data: dict[str, Any], *, base_url: str, default_file_name: str) -> UpdateAsset:
    raw_url = str(data.get("url") or "").strip()
    sha256 = str(data.get("sha256") or "").strip().lower()
    if not raw_url:
        raise UpdateError("Un asset del manifest no tiene URL.")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
        raise UpdateError("Un asset del manifest no tiene sha256 valido.")

    url = urljoin(base_url, raw_url)
    file_name = str(data.get("file_name") or "").strip()
    if not file_name:
        file_name = Path(raw_url.split("?", 1)[0].rstrip("/")).name or default_file_name
    file_name = re.sub(r"[^A-Za-z0-9._-]+", "-", file_name).strip(".-") or default_file_name
    size = data.get("size")
    safe_size = int(size) if isinstance(size, int) and size >= 0 else None
    return UpdateAsset(url=url, sha256=sha256, file_name=file_name, size=safe_size)


def compare_versions(left: str, right: str) -> int:
    left_parts = version_parts(left)
    right_parts = version_parts(right)
    max_len = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (max_len - len(left_parts)))
    right_parts.extend([0] * (max_len - len(right_parts)))
    if left_parts > right_parts:
        return 1
    if left_parts < right_parts:
        return -1
    return 0


def version_parts(value: str) -> list[int | str]:
    parts: list[int | str] = []
    for token in re.findall(r"\d+|[A-Za-z]+", value):
        if token.isdigit():
            parts.append(int(token))
        else:
            parts.append(token.lower())
    return parts or [0]


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
