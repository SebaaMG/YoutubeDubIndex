param(
    [string]$SourceDb = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Export-SqliteDatabase {
    param(
        [Parameter(Mandatory=$true)][string]$SourceDb,
        [Parameter(Mandatory=$true)][string]$DestinationDb
    )

    $env:PORTABLE_DB_SOURCE = $SourceDb
    $env:PORTABLE_DB_DEST = $DestinationDb
    @'
import os
import sqlite3
from pathlib import Path

source_path = Path(os.environ["PORTABLE_DB_SOURCE"])
destination_path = Path(os.environ["PORTABLE_DB_DEST"])
destination_path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = destination_path.with_name(destination_path.name + ".tmp")
if tmp_path.exists():
    tmp_path.unlink()

source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
target = sqlite3.connect(tmp_path)
try:
    source.backup(target)
finally:
    target.close()
    source.close()

tmp_path.replace(destination_path)
'@ | python -
}

function Get-CatalogUsefulCount {
    param([Parameter(Mandatory=$true)][string]$DbPath)

    $env:CATALOG_COUNT_DB = $DbPath
    $result = @'
import os
import sqlite3
from pathlib import Path

path = Path(os.environ["CATALOG_COUNT_DB"])
if not path.exists():
    print("0")
    raise SystemExit(0)
try:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2)
    count = conn.execute(
        """
        SELECT COUNT(DISTINCT v.video_id)
        FROM videos v
        JOIN video_audio_tracks t ON t.video_id = v.video_id
        WHERE v.catalog_visible = 1
          AND v.metadata_complete = 1
          AND v.has_dubbing = 1
          AND t.language_base = 'es'
          AND t.is_original_audio = 0
        """
    ).fetchone()[0]
    conn.close()
    print(int(count or 0))
except Exception:
    print("0")
'@ | python -
    return [int]($result.Trim())
}

$existingPortableDb = Join-Path $root "dist\YouTubeDubIndexer\data\dub_index_desktop.db"
$portableBackupDb = $null
if (Test-Path -LiteralPath $existingPortableDb) {
    $portableBackupDb = Join-Path ([System.IO.Path]::GetTempPath()) ("youtubeindex-portable-db-{0}.db" -f [System.Guid]::NewGuid().ToString("N"))
    Export-SqliteDatabase -SourceDb $existingPortableDb -DestinationDb $portableBackupDb
}

$distRoot = Join-Path $root "dist\YouTubeDubIndexer"
if (Test-Path -LiteralPath $distRoot) {
    Get-ChildItem -LiteralPath $distRoot -Recurse -Force -File |
        ForEach-Object { $_.Attributes = [System.IO.FileAttributes]::Normal }
}

python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm YouTubeDubIndexer.spec

$distData = Join-Path $root "dist\YouTubeDubIndexer\data"
$distDb = Join-Path $distData "dub_index_desktop.db"
$dbCandidates = @()
if ($portableBackupDb -and (Test-Path -LiteralPath $portableBackupDb)) {
    $dbCandidates += $portableBackupDb
}
if ($env:LOCALAPPDATA) {
    $dbCandidates += Join-Path $env:LOCALAPPDATA "YouTubeDubIndexer\data\dub_index_desktop.db"
}
$dbCandidates += Join-Path $root "data\dub_index_desktop.db"

if ($SourceDb) {
    if (-not (Test-Path -LiteralPath $SourceDb)) {
        throw "SourceDb does not exist: $SourceDb"
    }
    $sourceDb = $SourceDb
} else {
    $sourceDb = $dbCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Sort-Object @{ Expression = { Get-CatalogUsefulCount $_ }; Descending = $true }, @{ Expression = { (Get-Item -LiteralPath $_).LastWriteTimeUtc }; Descending = $true } |
        Select-Object -First 1
}
if ($sourceDb) {
    $sourceCount = Get-CatalogUsefulCount $sourceDb
    Export-SqliteDatabase -SourceDb $sourceDb -DestinationDb $distDb
    $destCount = Get-CatalogUsefulCount $distDb
    if ($destCount -ne $sourceCount) {
        throw "Portable database smoke check failed: source=$sourceCount destination=$destCount"
    }
    Write-Host "Included portable database: $distDb ($destCount useful catalog videos)"
} else {
    Write-Host "No existing database found to include; the app will create one on first launch."
}

if ($portableBackupDb -and (Test-Path -LiteralPath $portableBackupDb)) {
    Remove-Item -LiteralPath $portableBackupDb -Force
}

$workerExe = Join-Path $root "dist\YouTubeDubIndexer\YouTubeDubIndexerWorker.exe"
$internalWorkerExe = Join-Path $root "dist\YouTubeDubIndexer\_internal\YouTubeDubIndexerWorker.exe"
if (Test-Path -LiteralPath $workerExe) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $internalWorkerExe) -Force | Out-Null
    if (Test-Path -LiteralPath $internalWorkerExe) {
        Remove-Item -LiteralPath $internalWorkerExe -Force
    }
    Move-Item -LiteralPath $workerExe -Destination $internalWorkerExe -Force
}

Write-Host "Built: $root\\dist\\YouTubeDubIndexer\\YouTubeDubIndexer.exe"
