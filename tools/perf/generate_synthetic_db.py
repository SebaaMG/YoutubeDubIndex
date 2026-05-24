from __future__ import annotations

import argparse
import gc
import json
import random
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402


LANGUAGE_SETS = [
    ["en", "es-US"],
    ["en", "es-419"],
    ["en", "es-ES"],
    ["en", "fr-FR"],
    ["en", "de-DE"],
    ["en"],
]


def iso_day(index: int) -> str:
    base = datetime(2026, 4, 24, tzinfo=timezone.utc)
    return (base - timedelta(days=index % 5000)).date().isoformat()


def build(
    path: Path,
    rows: int,
    sources: int,
    *,
    chunk_size: int = 5000,
    progress=None,
) -> dict[str, object]:
    if path.exists():
        path.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    db = Database(path)
    db.initialize()
    rng = random.Random(20260424)
    now = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    chunks = 0
    safe_chunk_size = max(1, int(chunk_size))
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executemany(
            """
            INSERT INTO sources(type, label, value, enabled, max_candidates_per_run, created_at, updated_at)
            VALUES('search', ?, ?, 1, 1000, ?, ?)
            """,
            [(f"Fuente {i + 1}", f"synthetic source {i + 1}", now, now) for i in range(sources)],
        )
        source_ids = [row[0] for row in conn.execute("SELECT id FROM sources").fetchall()]

        video_batch = []
        source_batch = []
        track_batch = []
        search_batch = []
        for index in range(rows):
            video_id = f"synthetic-{index:07d}"
            title = f"Video sintetico {index:07d} sobre tema {index % 97}"
            channel = f"Canal {index % 997:03d}"
            published_at = iso_day(index)
            published_year = int(published_at[:4])
            view_count = rng.randrange(0, 20_000_000)
            languages = LANGUAGE_SETS[index % len(LANGUAGE_SETS)]
            has_dubbing = len(languages) > 1
            dub_kind = "automatic" if has_dubbing and index % 11 == 0 else "manual" if has_dubbing else "none"
            video_batch.append(
                (
                    video_id,
                    title,
                    channel,
                    f"chan-{index % 997:03d}",
                    rng.randrange(45, 14400),
                    f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    published_at,
                    view_count,
                    1 if has_dubbing else 0,
                    json.dumps(languages),
                    len(languages),
                    dub_kind,
                    "high" if dub_kind in {"automatic", "none"} else "medium",
                    json.dumps({"source": "synthetic"}),
                    4,
                    1,
                    published_year,
                    view_count,
                    1,
                    now,
                    rng.random(),
                    now,
                    now,
                    "ok",
                    None,
                )
            )
            source_id = source_ids[index % len(source_ids)]
            source_batch.append((source_id, video_id, now, now))
            search_batch.append((index + 1, video_id, title, channel))
            for lang in languages:
                base = lang.split("-", 1)[0].lower()
                is_spanish = 1 if base == "es" else 0
                is_original = 0 if is_spanish and has_dubbing else 1 if lang == languages[0] else 0
                track_batch.append(
                    (
                        video_id,
                        lang,
                        base,
                        "",
                        1 if dub_kind == "automatic" and is_spanish else 0,
                        is_original,
                        "synthetic",
                    )
                )

            if len(video_batch) >= safe_chunk_size:
                flush(conn, video_batch, source_batch, track_batch, search_batch)
                conn.commit()
                chunks += 1
                if progress is not None:
                    progress(
                        {
                            "event": "chunk",
                            "rows": index + 1,
                            "chunks": chunks,
                            "elapsed_seconds": round(time.perf_counter() - started, 3),
                            "db_bytes": path.stat().st_size if path.exists() else 0,
                        }
                    )
                video_batch.clear()
                source_batch.clear()
                track_batch.clear()
                search_batch.clear()
        flush(conn, video_batch, source_batch, track_batch, search_batch)
        if video_batch:
            conn.commit()
            chunks += 1
            if progress is not None:
                progress(
                    {
                        "event": "chunk",
                        "rows": rows,
                        "chunks": chunks,
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                        "db_bytes": path.stat().st_size if path.exists() else 0,
                    }
                )
        conn.execute(
            """
            INSERT OR REPLACE INTO source_stats(source_id, video_count)
            SELECT source_id, COUNT(*) FROM video_sources GROUP BY source_id
            """
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    gc.collect()
    summary = {
        "event": "complete",
        "path": str(path),
        "rows": rows,
        "sources": sources,
        "chunks": chunks,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "db_bytes": path.stat().st_size if path.exists() else 0,
    }
    return summary


def flush(
    conn: sqlite3.Connection,
    videos: list[tuple],
    video_sources: list[tuple],
    tracks: list[tuple],
    search_rows: list[tuple],
) -> None:
    if not videos:
        return
    conn.executemany(
        """
        INSERT INTO videos(
            video_id, title, channel, channel_id, duration_seconds, thumbnail_url,
            published_at, view_count, has_dubbing, audio_languages_json, audio_language_count,
            dub_kind, dub_confidence, dub_evidence_json, dub_classifier_version,
            catalog_visible, published_year, view_count_sort, metadata_complete, metadata_sort_at,
            random_key, last_seen_at, last_checked_at, inspect_status, inspect_error
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        videos,
    )
    conn.executemany(
        "INSERT INTO video_sources(source_id, video_id, first_seen_at, last_seen_at) VALUES(?, ?, ?, ?)",
        video_sources,
    )
    conn.executemany(
        """
        INSERT INTO video_audio_tracks(
            video_id, language_code, language_base, track_id, is_auto_dubbed, is_original_audio, evidence_source
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        tracks,
    )
    conn.executemany(
        "INSERT INTO video_search(rowid, video_id, title, channel) VALUES(?, ?, ?, ?)",
        search_rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--sources", type=int, default=40)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "synthetic_100k.db")
    parser.add_argument("--chunk-size", type=int, default=5000)
    parser.add_argument("--json-progress", action="store_true")
    parser.add_argument("--min-free-gb", type=float, default=0)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.min_free_gb > 0:
        free_bytes = shutil.disk_usage(args.out.parent).free
        required = int(args.min_free_gb * 1024 * 1024 * 1024)
        if free_bytes < required:
            raise SystemExit(
                f"Not enough free space for scale fixture: have={free_bytes} required={required}"
            )

    def emit(event: dict[str, object]) -> None:
        if args.json_progress:
            print(json.dumps(event, sort_keys=True), flush=True)

    summary = build(
        args.out,
        max(1, args.rows),
        max(1, args.sources),
        chunk_size=max(1, args.chunk_size),
        progress=emit if args.json_progress else None,
    )
    if not args.json_progress:
        print(args.out)
    else:
        print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
