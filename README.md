# Desktop YouTube Dub Finder

Desktop app nativa `PySide6` para Windows que indexa videos de YouTube con doblaje espanol confirmado.

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
- Catalogo principal `Descubrir`, con filtros de idioma, fecha, favoritos y tipo de dub
- Busqueda rapida por tema o canal: guarda el interes como seed permanente y encola 150 candidatos iniciales en background
- Boton `Explorar 200`: inspecciona hasta 200 candidatos por click usando el mismo algoritmo de descubrimiento
- Discovery con `yt-dlp`
- Deteccion de doblaje mediante `audioTracks` del watch page
- Filtro de tipo de dub: `Todos los dubs`, `IA` y `No IA`, sin mostrar origen no confirmado en el catalogo final
- Starter pack local y pool de descubrimiento incluido en el bundle
- Bundle `one-folder` con `node.exe` incluido

La app empaquetada migra automaticamente una base antigua si encuentra `data\` junto al `.exe` y aun no existe una DB en `%LOCALAPPDATA%`.

## Descubrimiento automatico

El crawler local no intenta indexar todo YouTube. Usa una mezcla simple de seeds para encontrar candidatos con mas probabilidad de servir como material reaccionable:

- 70% pool de contenido: busquedas amplias incluidas en `resources/discovery/content_pool_v1.json` mas busquedas/canales escritos por el usuario.
- 30% YouTube libre: starter videos y videos relacionados de dubs ya verificados.

El patron se aplica al elegir seeds de descubrimiento, no al orden final del catalogo. No hay ranking dinamico global ni recalculo sobre millones de filas; los candidatos se encolan y luego solo entran al feed si pasan la inspeccion de dub espanol confirmado.
