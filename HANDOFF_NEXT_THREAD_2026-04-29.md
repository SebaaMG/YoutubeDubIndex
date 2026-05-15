# DubIndex Desktop Handoff - 2026-04-29

This handoff is for continuing work on the Windows desktop version of DubIndex, the local YouTube dubbing indexer/catalog app. The user is likely to start a fresh GPT-5.5/Codex thread for performance reasons. Continue from this state, not from the older web app.

## Current Workspace

- Active desktop app folder:
  - `J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork`
- Original web/MVP folder, mostly historical now:
  - `J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que`
- The desktop fork is not currently a git repository. `git status` in the desktop fork returns:
  - `fatal: not a git repository (or any of the parent directories): .git`
- Shell environment:
  - Windows PowerShell
  - Python 3.11
  - PySide6 desktop app
  - PyInstaller packaging

## Product Goal

DubIndex should be a comfortable local desktop app for a streamer who wants to find and browse YouTube videos with dubbing/audio in multiple languages. The streamer should not feel like they are using an admin panel or scraping tool.

Target workflow:

1. Open the app.
2. Understand what to do quickly.
3. Add a YouTube channel or a search term.
4. Let the app scan.
5. Browse "Mis videos" / dubbed videos.

The app must remain local and public-only: no cookies, no YouTube login, no media download, only metadata inspection.

## Current Valid Build

Only the current build folders were kept. All old `dist-*`, `build-*`, `dist`, and `build` folders were deleted.

Keep:

- Current runnable bundle:
  - `J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork\dist-ui\YouTubeDubIndexer`
- Current exe:
  - `J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork\dist-ui\YouTubeDubIndexer\YouTubeDubIndexer.exe`
- Current build work folder:
  - `J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork\build-ui`

Latest known exe timestamp:

- `29-04-2026 20:44:58`

The normal `dist\YouTubeDubIndexer` folder no longer exists after cleanup. If the user asks "where is the exe?", link them to `dist-ui\YouTubeDubIndexer`.

## Build Command

From the desktop fork:

```powershell
python -m PyInstaller --noconfirm --distpath dist-ui --workpath build-ui YouTubeDubIndexer.spec
```

PyInstaller may emit warnings about `rapidfuzz.__pyinstaller`, `urllib3.contrib.emscripten`, `packaging`, or hidden imports. These have not blocked the build.

## Latest Verification

Run from:

```powershell
J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork
```

Latest relevant UI tests:

```powershell
python -m unittest tests.test_ui_catalog tests.test_ui_sources -v
```

Result:

- `Ran 32 tests`
- `OK`

Important nuance: during the UI tests, Qt timers sometimes print `sqlite3.OperationalError: unable to open database file` tracebacks after temporary test databases are already gone. The unittest result still ends in `OK`. Do not treat those printed traces as failing tests unless the final test result fails.

Useful narrower tests:

```powershell
python -m unittest tests.test_ui_catalog -v
python -m unittest tests.test_ui_sources -v
python -m unittest tests.test_repository tests.test_ui_catalog tests.test_youtube -v
```

## Current App Architecture

Important files:

- `main.py`
  - Desktop entrypoint.
- `app/ui.py`
  - Main PySide6 UI. This is the hottest file for the current work.
- `app/desktop_services.py`
  - Controller facade used by the UI.
- `app/repository.py`
  - SQLite persistence, catalog queries, filters, dubbing classification persistence.
- `app/db.py`
  - SQLite schema and migrations.
- `app/youtube.py`
  - YouTube metadata/audio-language inspection.
- `app/run_manager.py`
  - Discovery/inspection run flow.
- `YouTubeDubIndexer.spec`
  - PyInstaller spec.

Hot `app/ui.py` landmarks:

- `CatalogCard`: around line 749.
- `CatalogCardDelegate`: around line 1042.
- `_build_dashboard_tab`: around line 1695.
- `_build_sources_tab`: around line 1782.
- `_build_catalog_tab`: around line 2025.
- `refresh_catalog_filters`: around line 3019.

## Current UI Direction

The user has been iterating from screenshots and wants the UI to closely match the dark reference design:

- Top bar: compact dark header with DubIndex brand, nav, and a blue `Buscar ahora` button.
- Main nav labels:
  - `Inicio`
  - `Dónde buscar`
  - `Mis videos`
- Do not expose `Escaneos` as a primary nav item.
- Avoid admin-like language.
- Avoid oversized empty panels.
- Keep UI compact and streamer-friendly.
- It is acceptable to leave unused vertical space empty instead of stretching cards to fill the page.
- The user strongly notices visual mismatch, clipping, and overly large cards/buttons.

## Recent UI Changes Already Done

### Catalog / "Mis videos"

- Removed visual language tags/chips from each video card.
  - The filter by language still exists.
  - The card should show thumbnail, duration, favorite star on hover/favorite, title, channel, upload date, and open icon.
  - It should not show language chips like `EN-US`, `ES-US`, etc.
- Upload date under each video should be the real YouTube upload date, not scrape/discovery date.
- Existing old videos may show `Fecha desconocida` until the user runs `Buscar ahora` once with the new build, because old rows were inspected before `published_at` existed.
- `needs_inspection()` in `app/repository.py` was updated so videos missing `published_at` or `view_count` are treated as needing reinspection.
- Catalog filters include:
  - text search
  - language
  - sort by `Más recientes`, `Más antiguos`, `Más vistos`
  - year of upload
  - readable year range filters:
    - `Subidos desde`
    - `Subidos hasta`
- `Año de subida`, `Subidos desde`, and `Subidos hasta` use editable combo boxes with scrollable YouTube-valid years from current year down to 2005.
- The language filter defaults to Spanish group if available:
  - Spanish language group uses `SPANISH_LANGUAGE_FILTER`.
  - Spanish codes include `es-US`, `es`, `es-419`, `es-ES`.

### Inicio

- The user wanted the `Cómo funciona` block and metric cards compacted upward.
- Current direction:
  - `Cómo funciona` should be compact.
  - The three step cards should look closer to the reference, with low height and no giant internal blank space.
  - Metrics (`Videos con dub`, `Escaneados`, `Fuentes`) should be smaller and not stretch down to fill the window.
  - Empty page space below is fine.
- `Acciones rápidas` was explicitly removed.
- `Búsquedas activas` was removed.
- `Videos guardados` was renamed conceptually to `Escaneados`.
- `Estado de tu biblioteca` was removed.
- Recent/historical scan details should not dominate the page. If reintroduced, keep behind a compact "Más info" style expander/dropdown.

### Dónde buscar

Current intended layout:

- Left card: `Nueva búsqueda`
  - `Tipo`
  - contextual field:
    - if type is channel: label `Canal`, placeholder `Pega el link del canal o escribe @canal`
    - if type is search: label `Búsqueda`, placeholder asking for the search term
  - `Videos a revisar`
    - default initial value: `1000`
    - max: `10000`
    - remembers last used value
  - `Activa`
  - `Guardar búsqueda`
- No manual `Nombre corto` field.
  - Source name is autogenerated from the channel/search value.
- No `Limpiar` button.
- Right card: `Canales y búsquedas guardadas`
  - Scrollable table/list for saved sources.
  - Actions belong in this section, not somewhere ambiguous.
  - Actions should be explicit:
    - edit selected
    - pause/reactivate selected
    - delete selected
    - scan selected now
- Latest fix adjusted action row so buttons should not overflow or clip:
  - secondary buttons are fixed-size
  - primary scan button expands in a controlled way
  - table min-height was reduced to avoid pushing the layout too much

## User Feedback Patterns To Respect

The user often gives screenshot-specific feedback. Treat it literally.

Common complaints so far:

- "Too big and generic."
- "The catalog is trapped in a small box."
- "The controls are too far from their labels."
- "Selectors are visually broken / white-on-white / overlapping."
- "This should use the page space, but not inflate cards vertically."
- "Streamer flow should be simple."
- "Do not show technical/admin surfaces."
- "Buttons do not fit the sections."
- "The UI does not match the reference enough."

When adjusting UI:

- Make small, visual, targeted changes and rebuild the exe.
- Always give the user the current exe/folder path after rebuilding.
- If changing catalog cards, inspect both widget path (`CatalogCard`) and delegate path (`CatalogCardDelegate`). The visible grid currently uses the delegate/list-view path, so only editing `CatalogCard` may not affect what the user sees.

## Backend / Metadata State

The app stores data in SQLite. Important schema areas:

- `videos`
  - includes `published_at`, `published_year`, `view_count`, `view_count_sort`
  - includes dubbing metadata:
    - `has_dubbing`
    - `audio_languages_json`
    - `audio_language_count`
    - `dub_kind`
    - `catalog_visible`
    - `is_favorite`
- `video_audio_tracks`
  - normalized language rows used for filtering.
- `sources`
  - saved channel/search sources.
- `scrape_runs`
  - scan history, mostly secondary/hidden in UI.

`app/youtube.py`:

- Uses YouTube watch-page payload and yt-dlp fallback.
- Extracts:
  - audio languages
  - upload date
  - view count
  - metadata like channel/title/thumbnail when available.
- `InspectionResult.has_dubbing` is true when there is more than one audio language.

Likes/dislikes:

- Do not add "most likes/dislikes" unless explicitly revisiting the tradeoff.
- That metadata is not currently stored, and adding it reliably would add overhead and fragility.

## Known Caveats

- Existing DB rows may require a new scan to backfill upload dates. Tell the user to run `Buscar ahora` once with the current build if cards still show `Fecha desconocida`.
- This desktop fork is not under git, so be careful with destructive edits. There is no easy branch restore.
- Old build folders were deleted. The only current exe is under `dist-ui`.
- If the user asks to update "the exe", rebuild into `dist-ui` unless they specifically ask for a different output folder.
- If the app is open while rebuilding, PyInstaller may fail to remove/replace the bundle. Close the running exe first or build to a fresh dist folder.

## Suggested Next Steps For A Fresh Thread

1. Open this handoff first.
2. Work in:
   - `J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork`
3. Inspect `app/ui.py` before editing, especially the current visible delegate rendering.
4. If the user gives a screenshot, identify whether the issue is:
   - dashboard layout
   - sources layout
   - catalog delegate/card rendering
   - top bar/nav styling
5. Make narrowly scoped UI changes.
6. Run relevant tests.
7. Rebuild with PyInstaller to `dist-ui`.
8. Link:
   - `dist-ui\YouTubeDubIndexer`
   - `dist-ui\YouTubeDubIndexer\YouTubeDubIndexer.exe`

## Commands Cheat Sheet

Open project:

```powershell
cd J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork
```

Run selected UI tests:

```powershell
python -m unittest tests.test_ui_catalog tests.test_ui_sources -v
```

Run full tests:

```powershell
python -m unittest discover -s tests -v
```

Build exe:

```powershell
python -m PyInstaller --noconfirm --distpath dist-ui --workpath build-ui YouTubeDubIndexer.spec
```

Current exe:

```powershell
.\dist-ui\YouTubeDubIndexer\YouTubeDubIndexer.exe
```

List remaining build folders:

```powershell
Get-ChildItem -Directory | Where-Object { $_.Name -like 'dist*' -or $_.Name -like 'build*' }
```

Expected after cleanup:

- `build-ui`
- `dist-ui`

