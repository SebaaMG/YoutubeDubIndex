# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = Path.cwd()
vendor_node = project_root / "vendor" / "node" / "node.exe"

datas = []
if vendor_node.exists():
    datas.append((str(vendor_node), "vendor/node"))
starter_pack = project_root / "resources" / "starter" / "dubindex_seed.db"
if starter_pack.exists():
    datas.append((str(starter_pack), "resources/starter"))

datas += collect_data_files("yt_dlp")
hiddenimports = collect_submodules("yt_dlp")

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["fastapi", "jinja2", "uvicorn", "webview"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YouTubeDubIndexer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="YouTubeDubIndexer",
)
