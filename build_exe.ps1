$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm YouTubeDubIndexer.spec

Write-Host "Built: $root\\dist\\YouTubeDubIndexer\\YouTubeDubIndexer.exe"
