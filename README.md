# YouTubeDubIndex

YouTubeDubIndex is a Windows desktop app for finding YouTube videos that have Spanish audio tracks. It keeps a local SQLite catalog, inspects videos in the background, and lets you browse confirmed dubbed videos with a dense native UI.

The app is designed for creators and streamers who want a ready-to-browse pool of videos with Spanish dubbing before deciding what to watch, react to, or save.

## Features

- Native Windows UI built with PySide6.
- Local-first portable data model backed by SQLite.
- Confirmed Spanish dubbing catalog with filters for language, upload date, dub type, favorites, and maximum video duration.
- Manual discovery through `Explore 250`, with progress updates every inspection chunk.
- Optional automatic discovery every five minutes while the app is open.
- Separate discovery worker process so YouTube parsing, yt-dlp work, and SQLite writes do not block the UI.
- Thumbnail loading with backpressure and caching for smoother scrolling.
- Curated reaction-oriented discovery pool plus related-video expansion.
- One-folder portable Windows build with the worker executable stored under `_internal`.

## Download

Use the latest GitHub Release, download the Windows ZIP, extract it, and run:

```text
YouTubeDubIndexer.exe
```

The app stores portable data next to the executable in:

```text
data\dub_index_desktop.db
```

Keep the extracted folder together. The `_internal` directory contains bundled runtime files and the background worker used by the app.

## Running From Source

Requirements:

- Windows 10 or newer
- Python 3.11+
- Git

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Building The Portable App

```powershell
.\build_exe.ps1
```

Expected output:

```text
dist\YouTubeDubIndexer\YouTubeDubIndexer.exe
```

The build script copies a consistent SQLite database into the portable build when a source database is available. You can pass an explicit database if needed:

```powershell
.\build_exe.ps1 -SourceDb J:\path\to\dub_index_desktop.db
```

## Development Checks

```powershell
python -m pytest -q
python -m PyInstaller --noconfirm YouTubeDubIndexer.spec
```

Performance harnesses live in `tools/perf/` for catalog scrolling, repository queries, and UI-under-search checks.

## Notes

YouTubeDubIndex uses publicly available YouTube metadata and audio-track information through local tooling. It is not affiliated with YouTube. Videos only become visible in the catalog after local inspection confirms Spanish dubbing.
