# YouTube Dub Indexer Desktop

Desktop app nativa `PySide6` para Windows que indexa videos de YouTube con doblaje.

## Ejecutar con Python

```powershell
cd J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork
python -m pip install -r requirements.txt
python main.py
```

## Generar `.exe` autosuficiente

```powershell
cd J:\Users\SebaM\Documents\Codex\2026-04-21-hay-alguna-forma-de-hacer-que-desktop-fork
.\build_exe.ps1
```

Salida esperada:

```text
dist\YouTubeDubIndexer\YouTubeDubIndexer.exe
```

## Que incluye

- UI nativa `PySide6 Widgets`
- Persistencia local SQLite
  - modo Python: `data\dub_index_desktop.db` dentro del proyecto
  - `.exe` empaquetado: `%LOCALAPPDATA%\YouTubeDubIndexer\data\dub_index_desktop.db`
- Fuentes `channel` y `search`
- Runs manuales
- Catalogo con filtros
- Discovery con `yt-dlp`
- Deteccion de doblaje mediante `audioTracks` del watch page
- Bundle `one-folder` con `node.exe` incluido

La app empaquetada migra automaticamente una base antigua si encuentra `data\` junto al `.exe` y aun no existe una DB en `%LOCALAPPDATA%`.
