from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('channel', 'search')),
    label TEXT NOT NULL,
    value TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    max_candidates_per_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    candidates_found INTEGER NOT NULL DEFAULT 0,
    videos_checked INTEGER NOT NULL DEFAULT 0,
    dubbed_found INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    channel TEXT,
    channel_id TEXT,
    duration_seconds INTEGER,
    thumbnail_url TEXT,
    published_at TEXT,
    view_count INTEGER,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    dub_kind TEXT NOT NULL DEFAULT 'manual' CHECK(dub_kind IN ('none', 'manual', 'automatic')),
    dub_confidence TEXT NOT NULL DEFAULT 'low',
    dub_evidence_json TEXT,
    dub_classifier_version INTEGER NOT NULL DEFAULT 0,
    has_dubbing INTEGER,
    audio_languages_json TEXT,
    audio_language_count INTEGER,
    catalog_visible INTEGER NOT NULL DEFAULT 0,
    published_year INTEGER,
    view_count_sort INTEGER NOT NULL DEFAULT -1,
    metadata_complete INTEGER NOT NULL DEFAULT 0,
    metadata_sort_at TEXT,
    random_key REAL NOT NULL DEFAULT 0,
    last_seen_at TEXT NOT NULL,
    last_checked_at TEXT,
    inspect_status TEXT NOT NULL DEFAULT 'pending' CHECK(inspect_status IN ('pending', 'ok', 'failed')),
    inspect_error TEXT
);

CREATE TABLE IF NOT EXISTS video_sources (
    source_id INTEGER NOT NULL REFERENCES sources(id),
    video_id TEXT NOT NULL REFERENCES videos(video_id),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (source_id, video_id)
);

CREATE TABLE IF NOT EXISTS video_audio_tracks (
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    language_code TEXT NOT NULL,
    language_base TEXT NOT NULL,
    track_id TEXT NOT NULL DEFAULT '',
    is_auto_dubbed INTEGER,
    is_original_audio INTEGER,
    evidence_source TEXT NOT NULL DEFAULT 'stored',
    PRIMARY KEY (video_id, language_code, track_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS video_search
USING fts5(video_id UNINDEXED, title, channel, tokenize='trigram');

CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL CHECK(job_type IN ('discover_source', 'inspect_light', 'inspect_deep', 'metadata_refresh')),
    state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued', 'leased', 'done', 'failed')),
    priority INTEGER NOT NULL DEFAULT 100,
    not_before TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT,
    lease_expires_at TEXT,
    run_id INTEGER REFERENCES scrape_runs(id),
    payload_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL UNIQUE,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_scan_state (
    source_id INTEGER PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
    last_scan_at TEXT,
    next_scan_at TEXT,
    last_success_at TEXT,
    cooldown_until TEXT,
    cursor_json TEXT
);

CREATE TABLE IF NOT EXISTS source_stats (
    source_id INTEGER PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
    video_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_seeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_kind TEXT NOT NULL CHECK(seed_kind IN (
        'user_search', 'user_channel', 'starter_video', 'related_video', 'system_search', 'system_channel'
    )),
    source_type TEXT NOT NULL CHECK(source_type IN ('search', 'channel', 'video')),
    label TEXT NOT NULL,
    value TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 100,
    last_discovered_at TEXT,
    next_discovery_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(seed_kind, value)
);

CREATE TABLE IF NOT EXISTS candidate_frontier (
    video_id TEXT PRIMARY KEY,
    title TEXT,
    channel TEXT,
    channel_id TEXT,
    duration_seconds INTEGER,
    thumbnail_url TEXT,
    published_at TEXT,
    view_count INTEGER,
    state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued', 'inspecting', 'verified', 'rejected', 'failed')),
    priority INTEGER NOT NULL DEFAULT 100,
    score REAL NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    not_before TEXT NOT NULL,
    source_seed_id INTEGER REFERENCES discovery_seeds(id) ON DELETE SET NULL,
    discovered_from_video_id TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS discovery_edges (
    from_video_id TEXT NOT NULL,
    to_video_id TEXT NOT NULL,
    edge_type TEXT NOT NULL DEFAULT 'related',
    created_at TEXT NOT NULL,
    PRIMARY KEY (from_video_id, to_video_id, edge_type)
);

CREATE TABLE IF NOT EXISTS feed_state (
    video_id TEXT PRIMARY KEY REFERENCES videos(video_id) ON DELETE CASCADE,
    promoted_at TEXT NOT NULL,
    last_shown_at TEXT,
    shown_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'crawler'
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON sources(enabled);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON scrape_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_last_seen ON videos(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_has_dubbing ON videos(has_dubbing, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_favorite ON videos(is_favorite, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_dub_kind ON videos(dub_kind, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_view_count ON videos(view_count DESC);
CREATE INDEX IF NOT EXISTS idx_videos_catalog_recent ON videos(published_at DESC, last_seen_at DESC, video_id DESC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_views ON videos(view_count_sort DESC, published_at DESC, video_id DESC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_dub_recent ON videos(dub_kind, published_at DESC, last_seen_at DESC, video_id DESC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_dub_oldest ON videos(dub_kind, published_at ASC, last_seen_at ASC, video_id ASC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_dub_views ON videos(dub_kind, view_count_sort DESC, published_at DESC, video_id DESC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_dub_random ON videos(dub_kind, random_key, video_id) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_has_recent ON videos(has_dubbing, published_at DESC, last_seen_at DESC, video_id DESC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_year_recent ON videos(published_year DESC, published_at DESC, video_id DESC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_channel_recent ON videos(channel COLLATE NOCASE, published_at DESC, video_id DESC) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_catalog_random ON videos(random_key, video_id) WHERE catalog_visible = 1;
CREATE INDEX IF NOT EXISTS idx_videos_metadata_queue ON videos(metadata_complete, dub_classifier_version, metadata_sort_at, video_id) WHERE inspect_status = 'ok';
CREATE INDEX IF NOT EXISTS idx_video_sources_source ON video_sources(source_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_video_sources_video ON video_sources(video_id, source_id);
CREATE INDEX IF NOT EXISTS idx_video_audio_tracks_language_video ON video_audio_tracks(language_code, video_id);
CREATE INDEX IF NOT EXISTS idx_video_audio_tracks_base_video ON video_audio_tracks(language_base, video_id);
CREATE INDEX IF NOT EXISTS idx_video_audio_tracks_base_original_video ON video_audio_tracks(language_base, is_original_audio, video_id);
CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_claim ON scheduler_jobs(state, not_before, priority, id);
CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_lease ON scheduler_jobs(state, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_discovery_seeds_next ON discovery_seeds(enabled, next_discovery_at, priority, id);
CREATE INDEX IF NOT EXISTS idx_candidate_frontier_claim ON candidate_frontier(state, not_before, priority, score DESC, updated_at);
CREATE INDEX IF NOT EXISTS idx_candidate_frontier_seed ON candidate_frontier(source_seed_id, state);
CREATE INDEX IF NOT EXISTS idx_discovery_edges_to ON discovery_edges(to_video_id);
CREATE INDEX IF NOT EXISTS idx_feed_state_promoted ON feed_state(promoted_at DESC);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)
            conn.executescript(INDEXES)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(videos)").fetchall()
        }
        if "published_at" not in existing_columns:
            conn.execute("ALTER TABLE videos ADD COLUMN published_at TEXT")
        if "view_count" not in existing_columns:
            conn.execute("ALTER TABLE videos ADD COLUMN view_count INTEGER")
        if "is_favorite" not in existing_columns:
            conn.execute("ALTER TABLE videos ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
        if "dub_kind" not in existing_columns:
            conn.execute("ALTER TABLE videos ADD COLUMN dub_kind TEXT NOT NULL DEFAULT 'manual'")
        if "dub_classifier_version" not in existing_columns:
            conn.execute("ALTER TABLE videos ADD COLUMN dub_classifier_version INTEGER NOT NULL DEFAULT 0")
        added_derived_columns = False
        derived_columns = {
            "catalog_visible": "INTEGER NOT NULL DEFAULT 0",
            "published_year": "INTEGER",
            "view_count_sort": "INTEGER NOT NULL DEFAULT -1",
            "metadata_complete": "INTEGER NOT NULL DEFAULT 0",
            "metadata_sort_at": "TEXT",
            "random_key": "REAL NOT NULL DEFAULT 0",
            "dub_confidence": "TEXT NOT NULL DEFAULT 'low'",
            "dub_evidence_json": "TEXT",
        }
        for column, definition in derived_columns.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE videos ADD COLUMN {column} {definition}")
                added_derived_columns = True

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS video_audio_tracks (
                video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
                language_code TEXT NOT NULL,
                language_base TEXT NOT NULL,
                track_id TEXT NOT NULL DEFAULT '',
                is_auto_dubbed INTEGER,
                is_original_audio INTEGER,
                evidence_source TEXT NOT NULL DEFAULT 'stored',
                PRIMARY KEY (video_id, language_code, track_id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS video_search
            USING fts5(video_id UNINDEXED, title, channel, tokenize='trigram');

            CREATE TABLE IF NOT EXISTS scheduler_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL CHECK(job_type IN ('discover_source', 'inspect_light', 'inspect_deep', 'metadata_refresh')),
                state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued', 'leased', 'done', 'failed')),
                priority INTEGER NOT NULL DEFAULT 100,
                not_before TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                lease_owner TEXT,
                lease_expires_at TEXT,
                run_id INTEGER REFERENCES scrape_runs(id),
                payload_json TEXT NOT NULL DEFAULT '{}',
                idempotency_key TEXT NOT NULL UNIQUE,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_scan_state (
                source_id INTEGER PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
                last_scan_at TEXT,
                next_scan_at TEXT,
                last_success_at TEXT,
                cooldown_until TEXT,
                cursor_json TEXT
            );

            CREATE TABLE IF NOT EXISTS source_stats (
                source_id INTEGER PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
                video_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS app_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS discovery_seeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seed_kind TEXT NOT NULL CHECK(seed_kind IN (
                    'user_search', 'user_channel', 'starter_video', 'related_video', 'system_search', 'system_channel'
                )),
                source_type TEXT NOT NULL CHECK(source_type IN ('search', 'channel', 'video')),
                label TEXT NOT NULL,
                value TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 100,
                last_discovered_at TEXT,
                next_discovery_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(seed_kind, value)
            );

            CREATE TABLE IF NOT EXISTS candidate_frontier (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                channel TEXT,
                channel_id TEXT,
                duration_seconds INTEGER,
                thumbnail_url TEXT,
                published_at TEXT,
                view_count INTEGER,
                state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued', 'inspecting', 'verified', 'rejected', 'failed')),
                priority INTEGER NOT NULL DEFAULT 100,
                score REAL NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                not_before TEXT NOT NULL,
                source_seed_id INTEGER REFERENCES discovery_seeds(id) ON DELETE SET NULL,
                discovered_from_video_id TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_checked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS discovery_edges (
                from_video_id TEXT NOT NULL,
                to_video_id TEXT NOT NULL,
                edge_type TEXT NOT NULL DEFAULT 'related',
                created_at TEXT NOT NULL,
                PRIMARY KEY (from_video_id, to_video_id, edge_type)
            );

            CREATE TABLE IF NOT EXISTS feed_state (
                video_id TEXT PRIMARY KEY REFERENCES videos(video_id) ON DELETE CASCADE,
                promoted_at TEXT NOT NULL,
                last_shown_at TEXT,
                shown_count INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'crawler'
            );
            """
        )
        track_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(video_audio_tracks)").fetchall()
        }
        if "is_original_audio" not in track_columns:
            conn.execute("ALTER TABLE video_audio_tracks ADD COLUMN is_original_audio INTEGER")
        conn.execute(
            """
            INSERT OR IGNORE INTO discovery_seeds(
                seed_kind, source_type, label, value, enabled, priority, created_at, updated_at
            )
            SELECT
                CASE WHEN type = 'channel' THEN 'user_channel' ELSE 'user_search' END,
                type,
                label,
                value,
                enabled,
                50,
                created_at,
                updated_at
            FROM sources
            """
        )
        if added_derived_columns or conn.execute("SELECT COUNT(*) FROM video_search").fetchone()[0] == 0:
            conn.execute(
                """
                UPDATE videos
                SET published_year = CASE
                        WHEN published_at IS NOT NULL AND LENGTH(published_at) >= 4 THEN CAST(SUBSTR(published_at, 1, 4) AS INTEGER)
                        ELSE NULL
                    END,
                    view_count_sort = COALESCE(view_count, -1),
                    catalog_visible = CASE
                        WHEN inspect_status = 'ok' AND published_at IS NOT NULL AND published_at != '' THEN 1
                        ELSE 0
                    END,
                    metadata_complete = CASE
                        WHEN published_at IS NOT NULL AND published_at != ''
                         AND view_count IS NOT NULL
                         AND channel IS NOT NULL AND channel != '' THEN 1
                        ELSE 0
                    END,
                    metadata_sort_at = COALESCE(last_checked_at, last_seen_at),
                    random_key = CASE WHEN random_key = 0 THEN ABS(RANDOM()) / 9223372036854775807.0 ELSE random_key END
                """
            )
            conn.execute("DELETE FROM video_search")
            conn.execute(
                """
                INSERT INTO video_search(rowid, video_id, title, channel)
                SELECT rowid, video_id, title, COALESCE(channel, '') FROM videos
                """
            )
            conn.execute("DELETE FROM video_audio_tracks")
            conn.execute(
                """
                INSERT OR IGNORE INTO video_audio_tracks(video_id, language_code, language_base, track_id, evidence_source)
                SELECT videos.video_id,
                       json_each.value,
                       LOWER(CASE
                         WHEN INSTR(json_each.value, '-') > 0 THEN SUBSTR(json_each.value, 1, INSTR(json_each.value, '-') - 1)
                         ELSE json_each.value
                       END),
                       '',
                       'migration'
                FROM videos, json_each(COALESCE(videos.audio_languages_json, '[]'))
                WHERE json_each.value IS NOT NULL AND json_each.value != ''
                """
            )
        classifier_fix = conn.execute(
            "SELECT value FROM app_preferences WHERE key = 'dub_kind_classifier_v2'"
        ).fetchone()
        if classifier_fix is None:
            conn.execute(
                "INSERT INTO app_preferences(key, value) VALUES('dub_kind_classifier_v2', '1')"
            )
        classifier_fix_v3 = conn.execute(
            "SELECT value FROM app_preferences WHERE key = 'dub_kind_classifier_v3'"
        ).fetchone()
        if classifier_fix_v3 is None:
            conn.execute(
                "INSERT INTO app_preferences(key, value) VALUES('dub_kind_classifier_v3', '1')"
            )
        classifier_fix_v5 = conn.execute(
            "SELECT value FROM app_preferences WHERE key = 'dub_kind_classifier_v5_spanish_track_evidence'"
        ).fetchone()
        if classifier_fix_v5 is None:
            for row in conn.execute(
                "SELECT video_id, has_dubbing, dub_evidence_json FROM videos WHERE inspect_status = 'ok'"
            ).fetchall():
                video_id = row["video_id"]
                auto_languages: list[str] = []
                try:
                    evidence = json.loads(row["dub_evidence_json"] or "{}")
                except json.JSONDecodeError:
                    evidence = {}
                raw_auto_languages = evidence.get("auto_dubbed_languages") if isinstance(evidence, dict) else None
                if isinstance(raw_auto_languages, list):
                    auto_languages = [str(value) for value in raw_auto_languages if value]

                spanish_auto = any(language.lower().split("-", 1)[0] == "es" for language in auto_languages)
                if int(row["has_dubbing"] or 0):
                    conn.execute(
                        "UPDATE videos SET dub_kind = ?, dub_confidence = ? WHERE video_id = ?",
                        ("automatic" if spanish_auto else "manual", "high" if spanish_auto else "low", video_id),
                    )
                else:
                    conn.execute(
                        "UPDATE videos SET dub_kind = 'none', dub_confidence = 'high' WHERE video_id = ?",
                        (video_id,),
                    )
                conn.execute("UPDATE video_audio_tracks SET is_auto_dubbed = NULL WHERE video_id = ?", (video_id,))
                for language in auto_languages:
                    base = language.lower().split("-", 1)[0]
                    if base != "es":
                        continue
                    conn.execute(
                        """
                        UPDATE video_audio_tracks
                        SET is_auto_dubbed = 1
                        WHERE video_id = ? AND (language_code = ? OR language_base = ?)
                        """,
                        (video_id, language, base),
                    )
            conn.execute(
                "INSERT INTO app_preferences(key, value) VALUES('dub_kind_classifier_v5_spanish_track_evidence', '1')"
            )
