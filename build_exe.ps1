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

$existingPortableDb = Join-Path $root "dist\YouTubeDubIndexer\data\dub_index_desktop.db"
$portableBackupDb = $null
if (Test-Path -LiteralPath $existingPortableDb) {
    $portableBackupDb = Join-Path ([System.IO.Path]::GetTempPath()) ("youtubeindex-portable-db-{0}.db" -f [System.Guid]::NewGuid().ToString("N"))
    Export-SqliteDatabase -SourceDb $existingPortableDb -DestinationDb $portableBackupDb
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

$sourceDb = $dbCandidates |
    Where-Object { Test-Path -LiteralPath $_ } |
    Sort-Object { (Get-Item -LiteralPath $_).LastWriteTimeUtc } -Descending |
    Select-Object -First 1
if ($sourceDb) {
    Export-SqliteDatabase -SourceDb $sourceDb -DestinationDb $distDb
    Write-Host "Included portable database: $distDb"
} else {
    Write-Host "No existing database found to include; the app will create one on first launch."
}

if ($portableBackupDb -and (Test-Path -LiteralPath $portableBackupDb)) {
    Remove-Item -LiteralPath $portableBackupDb -Force
}

Write-Host "Built: $root\\dist\\YouTubeDubIndexer\\YouTubeDubIndexer.exe"
