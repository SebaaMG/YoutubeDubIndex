# YouTubeDubIndex

YouTubeDubIndex is a local Windows catalog for YouTube videos with inspected audio tracks. It starts from packaged seeds or searches/channels you add, checks candidate videos in a background worker, stores the results in SQLite, and lets you browse the reviewed catalog from a dense PySide6 UI.

The main use case is finding videos with Spanish audio and telling whether the Spanish track appears to be a manual multi-audio dub or YouTube automatic dubbing. YouTube exposes some of this metadata to playback clients, but not as a practical search/catalog view; this app builds that view locally. Other detected audio languages are stored too, so the catalog can be filtered beyond Spanish when the data exists.

The app is local-first: discovery, inspection results, favorites, and filters are stored in a portable SQLite database on your machine.

## How It Works

1. Start from the packaged starter database, packaged discovery seeds, or a channel/search you add.
2. Discovery collects candidate videos from YouTube search, channel listings, and related-video data.
3. A separate worker inspects candidates with YouTube metadata and `yt-dlp`, then stores audio languages, original-track hints, auto-dub markers, title, channel, upload date, views, duration, and thumbnails.
4. Reviewed videos with usable metadata become available in the catalog. Confirmed dubbed videos are shown by default, with an option to show all reviewed videos.
5. The catalog can be filtered by detected language, source, channel, upload year, duration, favorites, and dub type.

## Features

- Native Windows UI built with PySide6.
- Local SQLite catalog stored beside the app in portable builds.
- Language filters built from detected audio tracks, with Spanish grouped as a single option and other detected languages selectable individually.
- Manual vs automatic dub filtering for Spanish tracks.
- Search, source, channel, year, duration, sorting, and favorites filters.
- Manual discovery through `Explore 250`, plus optional automatic discovery every five minutes while the app is open.
- Separate discovery worker process so YouTube parsing, `yt-dlp` work, and SQLite writes do not block the UI.
- Thumbnail loading with backpressure and caching for smoother scrolling.
- Packaged starter database, discovery seeds, and related-video expansion.
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
.\build_exe.ps1 -SourceDb C:\path\to\dub_index_desktop.db
```

## Development Checks

```powershell
python -m pytest -q
python -m PyInstaller --noconfirm YouTubeDubIndexer.spec
```

Performance harnesses live in `tools/perf/` for catalog scrolling, repository queries, and UI-under-search checks.

## Notes

YouTubeDubIndex uses publicly available YouTube metadata and audio-track information through local tooling. It does not download video media and is not affiliated with YouTube. Videos only become visible in the normal catalog after local inspection.

The source tree includes a Windows Node.js runtime at `vendor/node/node.exe` so portable builds can provide the JavaScript runtime used by `yt-dlp`. If that file is absent, the app falls back to `node` on `PATH`.
