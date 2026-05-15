from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .db import Database


SPANISH_LANGUAGE_FILTER = "__spanish__"
SPANISH_LANGUAGE_CODES = ("es-US", "es", "es-419", "es-ES")
CURRENT_DUB_CLASSIFIER_VERSION = 9
INTERNAL_DISCOVERY_SOURCE_VALUE = "__auto_discovery__"
CATALOG_SEARCH_PROBE_LIMIT = 5_000
CATALOG_SEARCH_DENSE_MATCH_RATIO = 0.005
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def normalize_audio_language(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered.endswith("-desc") or "descriptive" in lowered:
        return None
    return text


def audio_language_base(value: str) -> str:
    return value.split("-", 1)[0].lower()


def published_year(value: str | None) -> int | None:
    text = str(value or "")
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def catalog_visible(inspect_status: str | None, published_at: str | None) -> int:
    return 1 if inspect_status == "ok" and bool(published_at) else 0


def metadata_complete(published_at: str | None, view_count: int | None, channel: str | None) -> int:
    return 1 if published_at and view_count is not None and bool((channel or "").strip()) else 0


def looks_like_video_id(value: str | None) -> bool:
    return bool(YOUTUBE_VIDEO_ID_RE.fullmatch(str(value or "").strip()))


def valid_video_title(video_id: str, title: str | None) -> bool:
    text = str(title or "").strip()
    return bool(text and not looks_like_video_id(text))


def valid_channel_name(video_id: str, title: str | None, channel: str | None) -> bool:
    text = str(channel or "").strip()
    title_text = str(title or "").strip()
    if not text or text == video_id:
        return False
    if title_text and text == title_text:
        return False
    return True


def metadata_values_complete(
    video_id: str,
    title: str | None,
    channel: str | None,
    published_at: str | None,
    view_count: int | None,
) -> int:
    return (
        1
        if published_at
        and view_count is not None
        and valid_video_title(video_id, title)
        and valid_channel_name(video_id, title, channel)
        else 0
    )


def sanitize_inspection_metadata(
    video_id: str,
    title: str | None,
    channel: str | None,
    channel_id: str | None,
) -> tuple[str | None, str | None, str | None]:
    title_text = str(title or "").strip()
    safe_title = title_text if valid_video_title(video_id, title_text) else None
    title_was_rejected = bool(title_text and safe_title is None)

    channel_text = str(channel or "").strip()
    safe_channel = None
    if not title_was_rejected and valid_channel_name(video_id, safe_title, channel_text):
        safe_channel = channel_text
    safe_channel_id = str(channel_id or "").strip() if safe_channel and str(channel_id or "").strip() else None
    return safe_title, safe_channel, safe_channel_id


def encode_cursor(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def normalize_audio_languages(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        language = normalize_audio_language(value)
        if language and language not in seen:
            seen.add(language)
            normalized.append(language)
    return sorted(normalized)


def effective_dub_kind(stored_kind: str | None, audio_languages: list[str]) -> str:
    languages = normalize_audio_languages(audio_languages)
    return effective_dub_kind_from_normalized(stored_kind, languages)


def effective_dub_kind_from_normalized(stored_kind: str | None, languages: list[str]) -> str:
    if len(languages) <= 1:
        return "none"
    if stored_kind == "automatic":
        return "automatic"
    if stored_kind == "manual":
        return "manual"
    if stored_kind == "none":
        return "none"
    return "manual"


def is_spanish_language(value: str | None) -> bool:
    return bool(value and audio_language_base(value) == "es")


def evidence_auto_dubbed_languages(evidence: dict[str, Any] | None) -> list[str]:
    if not isinstance(evidence, dict):
        return []
    raw = evidence.get("auto_dubbed_languages")
    if not isinstance(raw, list):
        return []
    return normalize_audio_languages([str(value) for value in raw])


def evidence_original_audio_languages(evidence: dict[str, Any] | None) -> list[str]:
    if not isinstance(evidence, dict):
        return []
    raw = evidence.get("original_audio_languages")
    if not isinstance(raw, list):
        return []
    return normalize_audio_languages([str(value) for value in raw])


def has_spanish_auto_dub(auto_dubbed_languages: list[str]) -> bool:
    return any(is_spanish_language(language) for language in auto_dubbed_languages)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime | None = None) -> str:
    value = dt or utc_now()
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@dataclass
class SourceInput:
    type: str
    label: str
    value: str
    max_candidates_per_run: int
    enabled: bool = True


@dataclass
class CandidateVideo:
    video_id: str
    title: str
    channel: str | None
    channel_id: str | None
    duration_seconds: int | None
    thumbnail_url: str | None
    source_id: int
    discovered_at: str
    published_at: str | None = None
    view_count: int | None = None


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _ensure_internal_discovery_source(self, conn: Any) -> int:
        row = conn.execute(
            "SELECT id FROM sources WHERE type = 'search' AND value = ?",
            (INTERNAL_DISCOVERY_SOURCE_VALUE,),
        ).fetchone()
        if row is not None:
            return int(row["id"])
        timestamp = to_iso()
        cursor = conn.execute(
            """
            INSERT INTO sources(type, label, value, enabled, max_candidates_per_run, created_at, updated_at)
            VALUES('search', 'Auto discovery', ?, 0, 1, ?, ?)
            """,
            (INTERNAL_DISCOVERY_SOURCE_VALUE, timestamp, timestamp),
        )
        return int(cursor.lastrowid)

    def _sync_video_search(self, conn: Any, video_id: str) -> None:
        row = conn.execute(
            "SELECT rowid, video_id, title, COALESCE(channel, '') AS channel FROM videos WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        if row is None:
            return
        conn.execute("DELETE FROM video_search WHERE video_id = ?", (video_id,))
        conn.execute(
            "INSERT INTO video_search(rowid, video_id, title, channel) VALUES (?, ?, ?, ?)",
            (row["rowid"], row["video_id"], row["title"], row["channel"]),
        )

    def _refresh_video_metadata_complete(self, conn: Any, video_id: str) -> None:
        row = conn.execute(
            """
            SELECT video_id, title, channel, published_at, view_count
            FROM videos
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()
        if row is None:
            return
        conn.execute(
            "UPDATE videos SET metadata_complete = ? WHERE video_id = ?",
            (
                metadata_values_complete(
                    str(row["video_id"]),
                    row["title"],
                    row["channel"],
                    row["published_at"],
                    row["view_count"],
                ),
                video_id,
            ),
        )

    def _replace_audio_tracks(
        self,
        conn: Any,
        video_id: str,
        languages: list[str],
        *,
        is_auto_dubbed: bool | None,
        auto_dubbed_languages: list[str] | None = None,
        original_audio_languages: list[str] | None = None,
        evidence_source: str,
    ) -> None:
        conn.execute("DELETE FROM video_audio_tracks WHERE video_id = ?", (video_id,))
        normalized_auto_languages = normalize_audio_languages(auto_dubbed_languages or [])
        normalized_original_languages = normalize_audio_languages(original_audio_languages or [])
        auto_language_codes = set(normalized_auto_languages)
        auto_language_bases = {audio_language_base(language) for language in normalized_auto_languages}
        original_language_codes = set(normalized_original_languages)
        original_language_bases = {audio_language_base(language) for language in normalized_original_languages}
        rows = [
            (
                video_id,
                language,
                audio_language_base(language),
                "",
                (
                    1
                    if language in auto_language_codes or audio_language_base(language) in auto_language_bases
                    else 1
                    if is_auto_dubbed is True and not normalized_auto_languages
                    else 0
                    if is_auto_dubbed is False
                    else None
                ),
                (
                    1
                    if language in original_language_codes or audio_language_base(language) in original_language_bases
                    else 0
                    if normalized_original_languages
                    else None
                ),
                evidence_source,
            )
            for language in normalize_audio_languages(languages)
        ]
        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO video_audio_tracks(
                    video_id, language_code, language_base, track_id,
                    is_auto_dubbed, is_original_audio, evidence_source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def _sync_source_stats(self, conn: Any, source_ids: list[int] | None = None) -> None:
        if source_ids is None:
            conn.execute("DELETE FROM source_stats")
            conn.execute(
                """
                INSERT OR REPLACE INTO source_stats(source_id, video_count)
                SELECT source_id, COUNT(*) FROM video_sources GROUP BY source_id
                """
            )
            return
        for source_id in source_ids:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_stats(source_id, video_count)
                VALUES (?, (SELECT COUNT(*) FROM video_sources WHERE source_id = ?))
                """,
                (source_id, source_id),
            )

    def _normalize_spanish_track_evidence(self, conn: Any, video_ids: list[str]) -> None:
        if not video_ids:
            return
        placeholders = ",".join("?" for _ in video_ids)
        rows = conn.execute(
            f"SELECT video_id, has_dubbing, dub_kind, dub_evidence_json FROM videos WHERE video_id IN ({placeholders})",
            video_ids,
        ).fetchall()
        for row in rows:
            video_id = str(row["video_id"])
            try:
                evidence = json.loads(row["dub_evidence_json"] or "{}")
            except json.JSONDecodeError:
                evidence = {}
            auto_dubbed_languages = evidence_auto_dubbed_languages(evidence)
            original_audio_languages = evidence_original_audio_languages(evidence)
            flagged_languages = [
                str(track["language_code"])
                for track in conn.execute(
                    """
                    SELECT language_code
                    FROM video_audio_tracks
                    WHERE video_id = ? AND language_base = 'es' AND is_auto_dubbed = 1
                    """,
                    (video_id,),
                ).fetchall()
            ]
            auto_dubbed_languages = normalize_audio_languages([*auto_dubbed_languages, *flagged_languages])
            if not auto_dubbed_languages and str(row["dub_kind"] or "") == "automatic":
                auto_dubbed_languages = [
                    str(track["language_code"])
                    for track in conn.execute(
                        """
                        SELECT language_code
                        FROM video_audio_tracks
                        WHERE video_id = ? AND language_base = 'es'
                        """,
                        (video_id,),
                    ).fetchall()
                ]
            spanish_auto_confirmed = has_spanish_auto_dub(auto_dubbed_languages)
            if int(row["has_dubbing"] or 0):
                conn.execute(
                    "UPDATE videos SET dub_kind = ?, dub_confidence = ? WHERE video_id = ?",
                    ("automatic" if spanish_auto_confirmed else "manual", "high" if spanish_auto_confirmed else "low", video_id),
                )
            else:
                conn.execute(
                    "UPDATE videos SET dub_kind = 'none', dub_confidence = 'high' WHERE video_id = ?",
                    (video_id,),
                )
            conn.execute("UPDATE video_audio_tracks SET is_auto_dubbed = NULL WHERE video_id = ?", (video_id,))
            for language in auto_dubbed_languages:
                if not is_spanish_language(language):
                    continue
                conn.execute(
                    """
                    UPDATE video_audio_tracks
                    SET is_auto_dubbed = 1
                    WHERE video_id = ? AND (language_code = ? OR language_base = ?)
                    """,
                    (video_id, language, audio_language_base(language)),
                )
            if original_audio_languages:
                conn.execute("UPDATE video_audio_tracks SET is_original_audio = 0 WHERE video_id = ?", (video_id,))
                for language in original_audio_languages:
                    conn.execute(
                        """
                        UPDATE video_audio_tracks
                        SET is_original_audio = 1
                        WHERE video_id = ? AND (language_code = ? OR language_base = ?)
                        """,
                        (video_id, language, audio_language_base(language)),
                    )

    def dashboard_stats(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            active_sources = conn.execute(
                "SELECT COUNT(*) FROM sources WHERE enabled = 1 AND value != ?",
                (INTERNAL_DISCOVERY_SOURCE_VALUE,),
            ).fetchone()[0]
            total_videos = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
            dubbed_videos = conn.execute(
                "SELECT COUNT(*) FROM videos WHERE has_dubbing = 1"
            ).fetchone()[0]
            latest_run = conn.execute(
                "SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            "active_sources": active_sources,
            "total_videos": total_videos,
            "dubbed_videos": dubbed_videos,
            "latest_run": dict(latest_run) if latest_run else None,
        }

    def list_sources(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.*,
                    COALESCE(source_counts.video_count, stats.video_count, 0) AS video_count,
                    CASE
                        WHEN COALESCE(source_counts.video_count, stats.video_count, 0) >= s.max_candidates_per_run THEN 1
                        ELSE 0
                    END AS is_full
                FROM sources s
                LEFT JOIN source_stats stats ON stats.source_id = s.id
                LEFT JOIN (
                    SELECT source_id, COUNT(*) AS video_count
                    FROM video_sources
                    GROUP BY source_id
                ) source_counts ON source_counts.source_id = s.id
                WHERE s.value != ?
                ORDER BY s.enabled DESC, s.updated_at DESC, s.id DESC
                """
                ,
                (INTERNAL_DISCOVERY_SOURCE_VALUE,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_source(self, source_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_source(self, source_id: int, *, delete_videos: bool = False) -> None:
        self.delete_sources([source_id], delete_videos=delete_videos)

    def delete_sources(self, source_ids: list[int], *, delete_videos: bool = False) -> None:
        if not source_ids:
            return
        params = ",".join("?" for _ in source_ids)
        with self.db.connect() as conn:
            video_ids_to_delete: list[str] = []
            if delete_videos:
                rows = conn.execute(
                    f"""
                    SELECT video_id
                    FROM video_sources
                    WHERE source_id IN ({params})
                    EXCEPT
                    SELECT video_id
                    FROM video_sources
                    WHERE source_id NOT IN ({params})
                    """,
                    tuple(source_ids) + tuple(source_ids),
                ).fetchall()
                video_ids_to_delete = [str(row["video_id"]) for row in rows]

            conn.execute(
                f"DELETE FROM video_sources WHERE source_id IN ({params})",
                tuple(source_ids),
            )
            conn.execute(
                f"DELETE FROM sources WHERE id IN ({params})",
                tuple(source_ids),
            )
            if video_ids_to_delete:
                video_params = ",".join("?" for _ in video_ids_to_delete)
                conn.execute(
                    f"DELETE FROM video_search WHERE video_id IN ({video_params})",
                    tuple(video_ids_to_delete),
                )
                conn.execute(
                    f"DELETE FROM videos WHERE video_id IN ({video_params})",
                    tuple(video_ids_to_delete),
                )
            conn.execute(
                f"DELETE FROM source_stats WHERE source_id IN ({params})",
                tuple(source_ids),
            )

    def create_source(self, payload: SourceInput) -> int:
        timestamp = to_iso()
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sources (type, label, value, enabled, max_candidates_per_run, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.type,
                    payload.label,
                    payload.value,
                    1 if payload.enabled else 0,
                    payload.max_candidates_per_run,
                    timestamp,
                    timestamp,
                ),
            )
            return int(cursor.lastrowid)

    def update_source(self, source_id: int, payload: SourceInput) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE sources
                SET type = ?, label = ?, value = ?, enabled = ?, max_candidates_per_run = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.type,
                    payload.label,
                    payload.value,
                    1 if payload.enabled else 0,
                    payload.max_candidates_per_run,
                    to_iso(),
                    source_id,
                ),
            )

    def set_source_enabled(self, source_id: int, enabled: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE sources SET enabled = ?, updated_at = ? WHERE id = ?",
                (1 if enabled else 0, to_iso(), source_id),
            )

    def increase_full_source_limits(self, amount: int = 500) -> int:
        increment = max(1, int(amount))
        timestamp = to_iso()
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id
                FROM sources s
                LEFT JOIN (
                    SELECT source_id, COUNT(*) AS video_count
                    FROM video_sources
                    GROUP BY source_id
                ) source_counts ON source_counts.source_id = s.id
                WHERE COALESCE(source_counts.video_count, 0) >= s.max_candidates_per_run
                """
            ).fetchall()
            source_ids = [int(row["id"]) for row in rows]
            if not source_ids:
                return 0

            params = ",".join("?" for _ in source_ids)
            conn.execute(
                f"""
                UPDATE sources
                SET max_candidates_per_run = max_candidates_per_run + ?,
                    updated_at = ?
                WHERE id IN ({params})
                """,
                (increment, timestamp, *source_ids),
            )
            return len(source_ids)

    def list_enabled_sources(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sources WHERE enabled = 1 AND value != ? ORDER BY id ASC",
                (INTERNAL_DISCOVERY_SOURCE_VALUE,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_preference(self, key: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_preferences WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def set_preference(self, key: str, value: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_preferences (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def repair_display_metadata_flags(self, *, version: str = "v1") -> int:
        preference_key = f"display_metadata_repair:{version}"
        if self.get_preference(preference_key) == "1":
            return 0
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE videos
                SET metadata_complete = 0
                WHERE metadata_complete = 1
                  AND (
                    (
                      LENGTH(TRIM(COALESCE(title, ''))) = 11
                      AND TRIM(COALESCE(title, '')) NOT GLOB '*[^A-Za-z0-9_-]*'
                    )
                    OR (
                      TRIM(COALESCE(title, '')) != ''
                      AND TRIM(COALESCE(channel, '')) = TRIM(COALESCE(title, ''))
                    )
                  )
                """
            )
            repaired = int(cursor.rowcount or 0)
            conn.execute(
                """
                INSERT INTO app_preferences (key, value)
                VALUES (?, '1')
                ON CONFLICT(key) DO UPDATE SET value = '1'
                """,
                (preference_key,),
            )
            return repaired

    def create_discovery_seed(
        self,
        *,
        seed_kind: str,
        source_type: str,
        label: str,
        value: str,
        priority: int = 100,
        enabled: bool = True,
    ) -> int:
        timestamp = to_iso()
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO discovery_seeds(
                    seed_kind, source_type, label, value, enabled, priority,
                    next_discovery_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(seed_kind, value) DO UPDATE SET
                    label = excluded.label,
                    enabled = excluded.enabled,
                    priority = MIN(discovery_seeds.priority, excluded.priority),
                    next_discovery_at = COALESCE(discovery_seeds.next_discovery_at, excluded.next_discovery_at),
                    updated_at = excluded.updated_at
                RETURNING id
                """,
                (
                    seed_kind,
                    source_type,
                    label,
                    value,
                    1 if enabled else 0,
                    int(priority),
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            return int(cursor.fetchone()["id"])

    def list_discovery_seeds(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM discovery_seeds
                ORDER BY priority ASC, updated_at DESC, id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def claim_discovery_seeds(self, *, limit: int = 1, randomize: bool = False) -> list[dict[str, Any]]:
        timestamp = to_iso()
        safe_limit = max(1, min(50, int(limit)))
        order_by = "RANDOM()" if randomize else "priority ASC, COALESCE(next_discovery_at, created_at) ASC, id ASC"
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM discovery_seeds
                WHERE enabled = 1
                  AND (next_discovery_at IS NULL OR next_discovery_at <= ?)
                ORDER BY {order_by}
                LIMIT ?
                """,
                (timestamp, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_discovery_seed_scanned(self, seed_id: int, *, delay_minutes: int = 240) -> None:
        timestamp = to_iso()
        next_time = to_iso(utc_now() + timedelta(minutes=max(1, int(delay_minutes))))
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE discovery_seeds
                SET last_discovered_at = ?, next_discovery_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (timestamp, next_time, timestamp, int(seed_id)),
            )

    def enqueue_candidate(
        self,
        candidate: dict[str, Any],
        *,
        source_seed_id: int | None = None,
        discovered_from_video_id: str | None = None,
        priority: int = 100,
        score: float = 0,
    ) -> None:
        video_id = str(candidate.get("video_id") or "").strip()
        if not video_id:
            return
        timestamp = to_iso()
        title = str(candidate.get("title") or video_id)
        with self.db.connect() as conn:
            source_id = self._ensure_internal_discovery_source(conn)
            parsed_view_count = candidate.get("view_count")
            try:
                view_count = int(parsed_view_count) if parsed_view_count is not None else None
            except (TypeError, ValueError):
                view_count = None
            parsed_duration = candidate.get("duration_seconds")
            try:
                duration_seconds = int(parsed_duration) if parsed_duration is not None else None
            except (TypeError, ValueError):
                duration_seconds = None
            published_at = candidate.get("published_at")
            year = published_year(str(published_at) if published_at else None)
            view_sort = view_count if view_count is not None else -1
            conn.execute(
                """
                INSERT INTO videos (
                    video_id, title, channel, channel_id, duration_seconds, thumbnail_url,
                    published_at, view_count, has_dubbing, audio_languages_json, audio_language_count,
                    catalog_visible, published_year, view_count_sort, metadata_complete, metadata_sort_at,
                    random_key, last_seen_at, last_checked_at, inspect_status, inspect_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 0, ?, ?, 0, ?,
                        ABS(RANDOM()) / 9223372036854775807.0, ?, NULL, 'pending', NULL)
                ON CONFLICT(video_id) DO UPDATE SET
                    title = COALESCE(excluded.title, videos.title),
                    channel = COALESCE(excluded.channel, videos.channel),
                    channel_id = COALESCE(excluded.channel_id, videos.channel_id),
                    duration_seconds = COALESCE(excluded.duration_seconds, videos.duration_seconds),
                    thumbnail_url = COALESCE(excluded.thumbnail_url, videos.thumbnail_url),
                    published_at = COALESCE(excluded.published_at, videos.published_at),
                    view_count = COALESCE(excluded.view_count, videos.view_count),
                    published_year = COALESCE(excluded.published_year, videos.published_year),
                    view_count_sort = CASE
                        WHEN excluded.view_count IS NOT NULL THEN excluded.view_count_sort
                        ELSE videos.view_count_sort
                    END,
                    metadata_sort_at = excluded.metadata_sort_at,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    video_id,
                    title,
                    candidate.get("channel"),
                    candidate.get("channel_id"),
                    duration_seconds,
                    candidate.get("thumbnail_url"),
                    published_at,
                    view_count,
                    year,
                    view_sort,
                    timestamp,
                    timestamp,
                ),
            )
            conn.execute(
                """
                INSERT INTO video_sources(source_id, video_id, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id, video_id) DO UPDATE SET last_seen_at = excluded.last_seen_at
                """,
                (source_id, video_id, timestamp, timestamp),
            )
            conn.execute(
                """
                INSERT INTO candidate_frontier(
                    video_id, title, channel, channel_id, duration_seconds, thumbnail_url,
                    published_at, view_count, state, priority, score, attempts, not_before,
                    source_seed_id, discovered_from_video_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, 0, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title = COALESCE(excluded.title, candidate_frontier.title),
                    channel = COALESCE(excluded.channel, candidate_frontier.channel),
                    channel_id = COALESCE(excluded.channel_id, candidate_frontier.channel_id),
                    duration_seconds = COALESCE(excluded.duration_seconds, candidate_frontier.duration_seconds),
                    thumbnail_url = COALESCE(excluded.thumbnail_url, candidate_frontier.thumbnail_url),
                    published_at = COALESCE(excluded.published_at, candidate_frontier.published_at),
                    view_count = COALESCE(excluded.view_count, candidate_frontier.view_count),
                    state = CASE
                        WHEN candidate_frontier.state IN ('verified', 'rejected') THEN candidate_frontier.state
                        ELSE 'queued'
                    END,
                    priority = MIN(candidate_frontier.priority, excluded.priority),
                    score = MAX(candidate_frontier.score, excluded.score),
                    not_before = MIN(candidate_frontier.not_before, excluded.not_before),
                    source_seed_id = COALESCE(excluded.source_seed_id, candidate_frontier.source_seed_id),
                    discovered_from_video_id = COALESCE(excluded.discovered_from_video_id, candidate_frontier.discovered_from_video_id),
                    updated_at = excluded.updated_at
                """,
                (
                    video_id,
                    title,
                    candidate.get("channel"),
                    candidate.get("channel_id"),
                    duration_seconds,
                    candidate.get("thumbnail_url"),
                    published_at,
                    view_count,
                    int(priority),
                    float(score),
                    timestamp,
                    source_seed_id,
                    discovered_from_video_id,
                    timestamp,
                    timestamp,
                ),
            )
            if discovered_from_video_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO discovery_edges(from_video_id, to_video_id, edge_type, created_at)
                    VALUES (?, ?, 'related', ?)
                    """,
                    (discovered_from_video_id, video_id, timestamp),
                )
            self._sync_video_search(conn, video_id)
            self._sync_source_stats(conn, [source_id])

    def claim_frontier_candidates(self, *, limit: int = 10) -> list[dict[str, Any]]:
        timestamp = to_iso()
        safe_limit = max(1, min(200, int(limit)))
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM candidate_frontier
                WHERE state IN ('queued', 'failed') AND not_before <= ?
                ORDER BY priority ASC, score DESC, updated_at ASC
                LIMIT ?
                """,
                (timestamp, safe_limit),
            ).fetchall()
            ids = [str(row["video_id"]) for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"""
                    UPDATE candidate_frontier
                    SET state = 'inspecting', attempts = attempts + 1, updated_at = ?
                    WHERE video_id IN ({placeholders})
                    """,
                    (timestamp, *ids),
                )
        return [dict(row) for row in rows]

    def list_frontier_candidates(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_frontier ORDER BY priority ASC, updated_at DESC, video_id ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_candidate_verified(self, video_id: str, *, source: str = "crawler") -> None:
        timestamp = to_iso()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE candidate_frontier
                SET state = 'verified', last_checked_at = ?, updated_at = ?, last_error = NULL
                WHERE video_id = ?
                """,
                (timestamp, timestamp, video_id),
            )
            conn.execute(
                """
                INSERT INTO feed_state(video_id, promoted_at, source)
                VALUES (?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET promoted_at = COALESCE(feed_state.promoted_at, excluded.promoted_at)
                """,
                (video_id, timestamp, source),
            )

    def mark_candidate_rejected(self, video_id: str, reason: str) -> None:
        timestamp = to_iso()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE candidate_frontier
                SET state = 'rejected', last_error = ?, last_checked_at = ?, updated_at = ?
                WHERE video_id = ?
                """,
                (reason[:500], timestamp, timestamp, video_id),
            )

    def mark_candidate_failed(self, video_id: str, error: str, *, delay_minutes: int = 60) -> None:
        timestamp = to_iso()
        retry_at = to_iso(utc_now() + timedelta(minutes=max(1, int(delay_minutes))))
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE candidate_frontier
                SET state = 'failed', last_error = ?, last_checked_at = ?, not_before = ?, updated_at = ?
                WHERE video_id = ?
                """,
                (error[:500], timestamp, retry_at, timestamp, video_id),
            )

    def merge_starter_pack(self, starter_db_path: Path, *, version: str) -> dict[str, Any]:
        if not starter_db_path.exists():
            return {"skipped": True, "reason": "missing", "inserted_videos": 0}
        preference_key = f"starter_pack_version:{version}"
        if self.get_preference(preference_key) == "1":
            return {"skipped": True, "reason": "already_merged", "inserted_videos": 0}

        timestamp = to_iso()
        with self.db.connect() as conn:
            conn.execute("ATTACH DATABASE ? AS starter", (str(starter_db_path),))
            starter_track_columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA starter.table_info(video_audio_tracks)").fetchall()
            }
            starter_video_ids = [
                str(row["video_id"])
                for row in conn.execute(
                    "SELECT video_id FROM starter.videos WHERE catalog_visible = 1"
                ).fetchall()
            ]
            before = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM videos
                    WHERE video_id IN (SELECT video_id FROM starter.videos WHERE catalog_visible = 1)
                    """
                ).fetchone()[0]
            )
            source_id = self._ensure_internal_discovery_source(conn)
            conn.execute(
                """
                INSERT OR IGNORE INTO videos(
                    video_id, title, channel, channel_id, duration_seconds, thumbnail_url,
                    published_at, view_count, is_favorite, dub_kind, dub_confidence,
                    dub_evidence_json, dub_classifier_version, has_dubbing, audio_languages_json,
                    audio_language_count, catalog_visible, published_year, view_count_sort,
                    metadata_complete, metadata_sort_at, random_key, last_seen_at,
                    last_checked_at, inspect_status, inspect_error
                )
                SELECT
                    video_id, title, channel, channel_id, duration_seconds, thumbnail_url,
                    published_at, view_count, 0, dub_kind, dub_confidence,
                    dub_evidence_json, dub_classifier_version, has_dubbing, audio_languages_json,
                    audio_language_count, catalog_visible, published_year, view_count_sort,
                    metadata_complete, metadata_sort_at,
                    CASE WHEN random_key = 0 THEN ABS(RANDOM()) / 9223372036854775807.0 ELSE random_key END,
                    COALESCE(last_seen_at, ?), COALESCE(last_checked_at, ?), inspect_status, inspect_error
                FROM starter.videos
                WHERE catalog_visible = 1
                """
                ,
                (timestamp, timestamp),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO video_sources(source_id, video_id, first_seen_at, last_seen_at)
                SELECT ?, video_id, ?, ?
                FROM starter.videos
                WHERE catalog_visible = 1
                """,
                (source_id, timestamp, timestamp),
            )
            if "is_original_audio" in starter_track_columns:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO video_audio_tracks(
                        video_id, language_code, language_base, track_id,
                        is_auto_dubbed, is_original_audio, evidence_source
                    )
                    SELECT
                        video_id, language_code, language_base, track_id,
                        is_auto_dubbed, is_original_audio, 'starter'
                    FROM starter.video_audio_tracks
                    WHERE video_id IN (SELECT video_id FROM starter.videos WHERE catalog_visible = 1)
                    """
                )
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO video_audio_tracks(
                        video_id, language_code, language_base, track_id, is_auto_dubbed, evidence_source
                    )
                    SELECT video_id, language_code, language_base, track_id, is_auto_dubbed, 'starter'
                    FROM starter.video_audio_tracks
                    WHERE video_id IN (SELECT video_id FROM starter.videos WHERE catalog_visible = 1)
                    """
                )
            conn.execute(
                """
                UPDATE video_audio_tracks
                SET is_auto_dubbed = (
                        SELECT st.is_auto_dubbed
                        FROM starter.video_audio_tracks st
                        WHERE st.video_id = video_audio_tracks.video_id
                          AND st.language_code = video_audio_tracks.language_code
                          AND st.track_id = video_audio_tracks.track_id
                    ),
                    evidence_source = 'starter'
                WHERE EXISTS (
                    SELECT 1
                    FROM starter.video_audio_tracks st
                    WHERE st.video_id = video_audio_tracks.video_id
                      AND st.language_code = video_audio_tracks.language_code
                      AND st.track_id = video_audio_tracks.track_id
                      AND st.is_auto_dubbed = 1
                )
                """
            )
            if "is_original_audio" in starter_track_columns:
                conn.execute(
                    """
                    UPDATE video_audio_tracks
                    SET is_original_audio = (
                            SELECT st.is_original_audio
                            FROM starter.video_audio_tracks st
                            WHERE st.video_id = video_audio_tracks.video_id
                              AND st.language_code = video_audio_tracks.language_code
                              AND st.track_id = video_audio_tracks.track_id
                        ),
                        evidence_source = 'starter'
                    WHERE EXISTS (
                        SELECT 1
                        FROM starter.video_audio_tracks st
                        WHERE st.video_id = video_audio_tracks.video_id
                          AND st.language_code = video_audio_tracks.language_code
                          AND st.track_id = video_audio_tracks.track_id
                          AND st.is_original_audio IS NOT NULL
                    )
                    """
                )
            self._normalize_spanish_track_evidence(conn, starter_video_ids)
            conn.execute(
                """
                INSERT OR IGNORE INTO feed_state(video_id, promoted_at, source)
                SELECT video_id, ?, 'starter'
                FROM starter.videos
                WHERE catalog_visible = 1
                """
                ,
                (timestamp,),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO discovery_seeds(
                    seed_kind, source_type, label, value, enabled, priority,
                    next_discovery_at, created_at, updated_at
                )
                SELECT 'starter_video', 'video', title, video_id, 1, 80, ?, ?, ?
                FROM starter.videos
                WHERE catalog_visible = 1 AND has_dubbing = 1
                """
                ,
                (timestamp, timestamp, timestamp),
            )
            conn.execute(
                """
                DELETE FROM video_search
                WHERE video_id IN (SELECT video_id FROM starter.videos WHERE catalog_visible = 1)
                """
            )
            conn.execute(
                """
                INSERT INTO video_search(rowid, video_id, title, channel)
                SELECT rowid, video_id, title, COALESCE(channel, '')
                FROM videos
                WHERE video_id IN (SELECT video_id FROM starter.videos WHERE catalog_visible = 1)
                """
            )
            after = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM videos
                    WHERE video_id IN (SELECT video_id FROM starter.videos WHERE catalog_visible = 1)
                    """
                ).fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO app_preferences(key, value)
                VALUES (?, '1')
                ON CONFLICT(key) DO UPDATE SET value = '1'
                """,
                (preference_key,),
            )
            self._sync_source_stats(conn, [source_id])
        return {"skipped": False, "inserted_videos": max(0, after - before)}

    def list_runs(self, limit: int = 25) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scrape_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM scrape_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def create_run(self, scope: str) -> int:
        timestamp = to_iso()
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scrape_runs (scope, status, started_at, finished_at, candidates_found, videos_checked, dubbed_found, error)
                VALUES (?, 'queued', ?, NULL, 0, 0, 0, NULL)
                """,
                (scope, timestamp),
            )
            return int(cursor.lastrowid)

    def mark_run_running(self, run_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE scrape_runs SET status = 'running', started_at = ? WHERE id = ?",
                (to_iso(), run_id),
            )

    def increment_run_metrics(
        self,
        run_id: int,
        *,
        candidates_found: int = 0,
        videos_checked: int = 0,
        dubbed_found: int = 0,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE scrape_runs
                SET candidates_found = candidates_found + ?,
                    videos_checked = videos_checked + ?,
                    dubbed_found = dubbed_found + ?
                WHERE id = ?
                """,
                (candidates_found, videos_checked, dubbed_found, run_id),
            )

    def finish_run(self, run_id: int, *, status: str, error: str | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE scrape_runs SET status = ?, finished_at = ?, error = ? WHERE id = ?",
                (status, to_iso(), error, run_id),
            )

    def upsert_candidate(self, candidate: CandidateVideo) -> None:
        year = published_year(candidate.published_at)
        view_sort = candidate.view_count if candidate.view_count is not None else -1
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    video_id, title, channel, channel_id, duration_seconds, thumbnail_url,
                    published_at, view_count, has_dubbing, audio_languages_json, audio_language_count,
                    catalog_visible, published_year, view_count_sort, metadata_complete, metadata_sort_at,
                    random_key, last_seen_at, last_checked_at, inspect_status, inspect_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 0, ?, ?, 0, ?, ABS(RANDOM()) / 9223372036854775807.0, ?, NULL, 'pending', NULL)
                ON CONFLICT(video_id) DO UPDATE SET
                    title = CASE
                        WHEN excluded.title = videos.video_id THEN videos.title
                        ELSE excluded.title
                    END,
                    channel = CASE
                        WHEN excluded.title = videos.video_id THEN videos.channel
                        WHEN excluded.channel = excluded.title THEN videos.channel
                        WHEN excluded.channel = videos.video_id THEN videos.channel
                        ELSE COALESCE(excluded.channel, videos.channel)
                    END,
                    channel_id = COALESCE(excluded.channel_id, videos.channel_id),
                    duration_seconds = COALESCE(excluded.duration_seconds, videos.duration_seconds),
                    thumbnail_url = COALESCE(excluded.thumbnail_url, videos.thumbnail_url),
                    published_at = COALESCE(excluded.published_at, videos.published_at),
                    view_count = COALESCE(excluded.view_count, videos.view_count),
                    published_year = COALESCE(excluded.published_year, videos.published_year),
                    view_count_sort = CASE
                        WHEN excluded.view_count IS NOT NULL THEN excluded.view_count_sort
                        ELSE videos.view_count_sort
                    END,
                    metadata_complete = CASE
                        WHEN COALESCE(excluded.published_at, videos.published_at) IS NOT NULL
                         AND COALESCE(excluded.published_at, videos.published_at) != ''
                         AND COALESCE(excluded.view_count, videos.view_count) IS NOT NULL
                         AND COALESCE(NULLIF(excluded.title, ''), videos.title) != videos.video_id
                         AND COALESCE(excluded.channel, videos.channel) IS NOT NULL
                         AND COALESCE(excluded.channel, videos.channel) != ''
                         AND COALESCE(excluded.channel, videos.channel) != COALESCE(NULLIF(excluded.title, ''), videos.title)
                         AND COALESCE(excluded.channel, videos.channel) != videos.video_id THEN 1
                        ELSE 0
                    END,
                    metadata_sort_at = excluded.metadata_sort_at,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    candidate.video_id,
                    candidate.title,
                    candidate.channel,
                    candidate.channel_id,
                    candidate.duration_seconds,
                    candidate.thumbnail_url,
                    candidate.published_at,
                    candidate.view_count,
                    year,
                    view_sort,
                    candidate.discovered_at,
                    candidate.discovered_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO video_sources (source_id, video_id, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id, video_id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    candidate.source_id,
                    candidate.video_id,
                    candidate.discovered_at,
                    candidate.discovered_at,
                ),
            )
            self._sync_video_search(conn, candidate.video_id)
            self._sync_source_stats(conn, [candidate.source_id])

    def upsert_candidates_batch(self, candidates: list[CandidateVideo]) -> None:
        if not candidates:
            return
        source_ids: set[int] = set()
        with self.db.connect() as conn:
            for candidate in candidates:
                year = published_year(candidate.published_at)
                view_sort = candidate.view_count if candidate.view_count is not None else -1
                conn.execute(
                    """
                    INSERT INTO videos (
                        video_id, title, channel, channel_id, duration_seconds, thumbnail_url,
                        published_at, view_count, has_dubbing, audio_languages_json, audio_language_count,
                        catalog_visible, published_year, view_count_sort, metadata_complete, metadata_sort_at,
                        random_key, last_seen_at, last_checked_at, inspect_status, inspect_error
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 0, ?, ?, 0, ?, ABS(RANDOM()) / 9223372036854775807.0, ?, NULL, 'pending', NULL)
                    ON CONFLICT(video_id) DO UPDATE SET
                        title = CASE
                            WHEN excluded.title = videos.video_id THEN videos.title
                            ELSE excluded.title
                        END,
                        channel = CASE
                            WHEN excluded.title = videos.video_id THEN videos.channel
                            WHEN excluded.channel = excluded.title THEN videos.channel
                            WHEN excluded.channel = videos.video_id THEN videos.channel
                            ELSE COALESCE(excluded.channel, videos.channel)
                        END,
                        channel_id = COALESCE(excluded.channel_id, videos.channel_id),
                        duration_seconds = COALESCE(excluded.duration_seconds, videos.duration_seconds),
                        thumbnail_url = COALESCE(excluded.thumbnail_url, videos.thumbnail_url),
                        published_at = COALESCE(excluded.published_at, videos.published_at),
                        view_count = COALESCE(excluded.view_count, videos.view_count),
                        published_year = COALESCE(excluded.published_year, videos.published_year),
                        view_count_sort = CASE
                            WHEN excluded.view_count IS NOT NULL THEN excluded.view_count_sort
                            ELSE videos.view_count_sort
                        END,
                        metadata_complete = CASE
                            WHEN COALESCE(excluded.published_at, videos.published_at) IS NOT NULL
                             AND COALESCE(excluded.published_at, videos.published_at) != ''
                             AND COALESCE(excluded.view_count, videos.view_count) IS NOT NULL
                             AND COALESCE(NULLIF(excluded.title, ''), videos.title) != videos.video_id
                             AND COALESCE(excluded.channel, videos.channel) IS NOT NULL
                             AND COALESCE(excluded.channel, videos.channel) != ''
                             AND COALESCE(excluded.channel, videos.channel) != COALESCE(NULLIF(excluded.title, ''), videos.title)
                             AND COALESCE(excluded.channel, videos.channel) != videos.video_id THEN 1
                            ELSE 0
                        END,
                        metadata_sort_at = excluded.metadata_sort_at,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        candidate.video_id,
                        candidate.title,
                        candidate.channel,
                        candidate.channel_id,
                        candidate.duration_seconds,
                        candidate.thumbnail_url,
                        candidate.published_at,
                        candidate.view_count,
                        year,
                        view_sort,
                        candidate.discovered_at,
                        candidate.discovered_at,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO video_sources (source_id, video_id, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(source_id, video_id) DO UPDATE SET
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        candidate.source_id,
                        candidate.video_id,
                        candidate.discovered_at,
                        candidate.discovered_at,
                    ),
                )
                self._sync_video_search(conn, candidate.video_id)
                source_ids.add(int(candidate.source_id))
            self._sync_source_stats(conn, sorted(source_ids))

    def needs_inspection(
        self,
        video_id: str,
        stale_days: int,
        classifier_version: int = CURRENT_DUB_CLASSIFIER_VERSION,
    ) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT last_checked_at, inspect_status, published_at, view_count, channel, dub_classifier_version
                FROM videos
                WHERE video_id = ?
                """,
                (video_id,),
            ).fetchone()
        if row is None:
            return True
        last_checked = from_iso(row["last_checked_at"])
        if row["inspect_status"] == "failed":
            return True
        if not row["published_at"] or row["view_count"] is None or not row["channel"]:
            return True
        if int(row["dub_classifier_version"] or 0) < int(classifier_version):
            return True
        if not last_checked:
            return True
        return last_checked < (utc_now() - timedelta(days=stale_days))

    def select_inspection_needed(
        self,
        video_ids: list[str],
        stale_days: int,
        classifier_version: int = CURRENT_DUB_CLASSIFIER_VERSION,
    ) -> set[str]:
        if not video_ids:
            return set()
        placeholders = ",".join("?" for _ in video_ids)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT video_id, last_checked_at, inspect_status, metadata_complete, dub_classifier_version
                FROM videos
                WHERE video_id IN ({placeholders})
                """,
                video_ids,
            ).fetchall()
        found = {str(row["video_id"]): row for row in rows}
        stale_before = utc_now() - timedelta(days=stale_days)
        needed: set[str] = set()
        for video_id in video_ids:
            row = found.get(video_id)
            if row is None:
                needed.add(video_id)
                continue
            last_checked = from_iso(row["last_checked_at"])
            if row["inspect_status"] == "failed":
                needed.add(video_id)
            elif int(row["metadata_complete"] or 0) == 0:
                needed.add(video_id)
            elif int(row["dub_classifier_version"] or 0) < int(classifier_version):
                needed.add(video_id)
            elif not last_checked or last_checked < stale_before:
                needed.add(video_id)
        return needed

    def list_video_ids_missing_metadata(
        self,
        *,
        source_id: int | None = None,
        limit: int = 50,
        classifier_version: int = CURRENT_DUB_CLASSIFIER_VERSION,
    ) -> list[str]:
        clauses = [
            "v.inspect_status = 'ok'",
            "("
            "v.metadata_complete = 0 "
            "OR COALESCE(v.dub_classifier_version, 0) < ? "
            "OR v.title = v.video_id "
            "OR COALESCE(v.channel, '') = v.title "
            "OR EXISTS ("
            "SELECT 1 FROM video_audio_tracks t "
            "WHERE t.video_id = v.video_id AND t.language_base = 'es' AND t.is_original_audio IS NULL"
            ")"
            ")",
        ]
        params: list[Any] = [int(classifier_version)]
        if source_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM video_sources vs WHERE vs.video_id = v.video_id AND vs.source_id = ?)"
            )
            params.append(source_id)
        params.append(max(1, int(limit)))
        sql = f"""
            SELECT v.video_id
            FROM videos v
            WHERE {' AND '.join(clauses)}
            ORDER BY
                CASE
                    WHEN v.title = v.video_id OR COALESCE(v.channel, '') = v.title THEN 0
                    WHEN EXISTS (
                        SELECT 1 FROM video_audio_tracks t
                        WHERE t.video_id = v.video_id AND t.language_base = 'es' AND t.is_original_audio IS NULL
                    ) THEN 1
                    ELSE 2
                END,
                COALESCE(v.metadata_sort_at, v.last_checked_at, v.last_seen_at) ASC
            LIMIT ?
        """
        with self.db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [str(row["video_id"]) for row in rows]

    def count_videos_missing_metadata(
        self,
        *,
        classifier_version: int = CURRENT_DUB_CLASSIFIER_VERSION,
    ) -> int:
        with self.db.connect() as conn:
            return int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM videos
                    WHERE inspect_status = 'ok'
                      AND (
                          metadata_complete = 0
                          OR COALESCE(dub_classifier_version, 0) < ?
                          OR title = video_id
                          OR COALESCE(channel, '') = title
                          OR EXISTS (
                              SELECT 1 FROM video_audio_tracks t
                              WHERE t.video_id = videos.video_id
                                AND t.language_base = 'es'
                                AND t.is_original_audio IS NULL
                          )
                      )
                    """,
                    (int(classifier_version),),
                ).fetchone()[0]
            )

    def set_video_favorite(self, video_id: str, is_favorite: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE videos SET is_favorite = ? WHERE video_id = ?",
                (1 if is_favorite else 0, video_id),
            )

    def store_inspection_result(
        self,
        video_id: str,
        *,
        audio_languages: list[str],
        has_dubbing: bool,
        published_at: str | None = None,
        view_count: int | None = None,
        dub_kind: str | None = None,
        title: str | None = None,
        channel: str | None = None,
        channel_id: str | None = None,
        duration_seconds: int | None = None,
        thumbnail_url: str | None = None,
        dub_confidence: str | None = None,
        dub_evidence: dict[str, Any] | None = None,
        classifier_version: int = CURRENT_DUB_CLASSIFIER_VERSION,
    ) -> None:
        normalized_languages = normalize_audio_languages(audio_languages)
        safe_has_dubbing = bool(has_dubbing and len(normalized_languages) > 1)
        evidence_dict = dub_evidence or {"source": "inspection", "languages": normalized_languages}
        auto_dubbed_languages = evidence_auto_dubbed_languages(evidence_dict)
        original_audio_languages = evidence_original_audio_languages(evidence_dict)
        if not auto_dubbed_languages and dub_kind == "automatic":
            auto_dubbed_languages = [language for language in normalized_languages if is_spanish_language(language)]
        spanish_auto_confirmed = has_spanish_auto_dub(auto_dubbed_languages)
        safe_dub_kind = dub_kind if dub_kind in {"none", "manual", "automatic"} else None
        if safe_dub_kind is None:
            safe_dub_kind = "manual" if safe_has_dubbing else "none"
        if safe_has_dubbing and spanish_auto_confirmed:
            safe_dub_kind = "automatic"
        elif safe_dub_kind == "automatic":
            safe_dub_kind = "manual" if safe_has_dubbing else "none"
        safe_dub_kind = effective_dub_kind(safe_dub_kind, normalized_languages)
        final_published_year = published_year(published_at)
        final_view_count_sort = view_count if view_count is not None else None
        confidence = dub_confidence
        if confidence not in {"high", "medium", "low"}:
            confidence = "high" if safe_dub_kind in {"none", "automatic"} else "low"
        evidence_json = json.dumps(evidence_dict)
        safe_title, safe_channel, safe_channel_id = sanitize_inspection_metadata(
            video_id,
            title,
            channel,
            channel_id,
        )
        checked_at = to_iso()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE videos
                SET has_dubbing = ?,
                    audio_languages_json = ?,
                    audio_language_count = ?,
                    dub_kind = ?,
                    dub_confidence = ?,
                    dub_evidence_json = ?,
                    dub_classifier_version = ?,
                    title = COALESCE(NULLIF(?, ''), title),
                    channel = COALESCE(NULLIF(?, ''), channel),
                    channel_id = COALESCE(NULLIF(?, ''), channel_id),
                    duration_seconds = COALESCE(?, duration_seconds),
                    thumbnail_url = COALESCE(NULLIF(?, ''), thumbnail_url),
                    published_at = COALESCE(?, published_at),
                    view_count = COALESCE(?, view_count),
                    published_year = COALESCE(?, published_year),
                    view_count_sort = COALESCE(?, view_count_sort),
                    catalog_visible = CASE
                        WHEN COALESCE(?, published_at) IS NOT NULL AND COALESCE(?, published_at) != '' THEN 1
                        ELSE 0
                    END,
                    metadata_complete = CASE
                        WHEN COALESCE(?, published_at) IS NOT NULL AND COALESCE(?, published_at) != ''
                         AND COALESCE(?, view_count) IS NOT NULL
                         AND COALESCE(NULLIF(?, ''), title) != video_id
                         AND COALESCE(NULLIF(?, ''), channel) IS NOT NULL
                         AND COALESCE(NULLIF(?, ''), channel) != ''
                         AND COALESCE(NULLIF(?, ''), channel) != COALESCE(NULLIF(?, ''), title)
                         AND COALESCE(NULLIF(?, ''), channel) != video_id THEN 1
                        ELSE 0
                    END,
                    metadata_sort_at = ?,
                    last_checked_at = ?,
                    inspect_status = 'ok',
                    inspect_error = NULL
                WHERE video_id = ?
                """,
                (
                    1 if safe_has_dubbing else 0,
                    json.dumps(normalized_languages),
                    len(normalized_languages),
                    safe_dub_kind,
                    confidence,
                    evidence_json,
                    int(classifier_version),
                    safe_title,
                    safe_channel,
                    safe_channel_id,
                    duration_seconds,
                    thumbnail_url,
                    published_at,
                    view_count,
                    final_published_year,
                    final_view_count_sort,
                    published_at,
                    published_at,
                    published_at,
                    published_at,
                    view_count,
                    safe_title,
                    safe_channel,
                    safe_channel,
                    safe_channel,
                    safe_title,
                    safe_channel,
                    checked_at,
                    checked_at,
                    video_id,
                ),
            )
            conn.execute(
                """
                UPDATE candidate_frontier
                SET title = COALESCE(NULLIF(?, ''), title),
                    channel = COALESCE(NULLIF(?, ''), channel),
                    channel_id = COALESCE(NULLIF(?, ''), channel_id),
                    duration_seconds = COALESCE(?, duration_seconds),
                    thumbnail_url = COALESCE(NULLIF(?, ''), thumbnail_url),
                    published_at = COALESCE(?, published_at),
                    view_count = COALESCE(?, view_count),
                    updated_at = ?
                WHERE video_id = ?
                """,
                (
                    safe_title,
                    safe_channel,
                    safe_channel_id,
                    duration_seconds,
                    thumbnail_url,
                    published_at,
                    view_count,
                    checked_at,
                    video_id,
                ),
            )
            self._replace_audio_tracks(
                conn,
                video_id,
                normalized_languages,
                is_auto_dubbed=None,
                auto_dubbed_languages=auto_dubbed_languages,
                original_audio_languages=original_audio_languages,
                evidence_source=str(evidence_dict.get("source") or "inspection"),
            )
            self._refresh_video_metadata_complete(conn, video_id)
            self._sync_video_search(conn, video_id)

    def store_inspection_failure(self, video_id: str, error: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE videos
                SET last_checked_at = ?,
                    catalog_visible = 0,
                    metadata_sort_at = ?,
                    inspect_status = 'failed',
                    inspect_error = ?
                WHERE video_id = ?
                """,
                (to_iso(), to_iso(), error[:500], video_id),
            )

    def store_inspection_results_batch(self, results: list[dict[str, Any]]) -> None:
        if not results:
            return
        with self.db.connect() as conn:
            for result in results:
                payload = dict(result)
                video_id = str(payload.pop("video_id"))
                audio_languages = list(payload.pop("audio_languages"))
                has_dubbing = bool(payload.pop("has_dubbing"))
                published_at = payload.pop("published_at", None)
                view_count = payload.pop("view_count", None)
                dub_kind = payload.pop("dub_kind", None)
                title = payload.pop("title", None)
                channel = payload.pop("channel", None)
                channel_id = payload.pop("channel_id", None)
                duration_seconds = payload.pop("duration_seconds", None)
                thumbnail_url = payload.pop("thumbnail_url", None)
                dub_confidence = payload.pop("dub_confidence", None)
                dub_evidence = payload.pop("dub_evidence", None)
                classifier_version = int(payload.pop("classifier_version", CURRENT_DUB_CLASSIFIER_VERSION))

                normalized_languages = normalize_audio_languages(audio_languages)
                safe_has_dubbing = bool(has_dubbing and len(normalized_languages) > 1)
                evidence_dict = dub_evidence or {"source": "inspection", "languages": normalized_languages}
                auto_dubbed_languages = evidence_auto_dubbed_languages(evidence_dict)
                original_audio_languages = evidence_original_audio_languages(evidence_dict)
                if not auto_dubbed_languages and dub_kind == "automatic":
                    auto_dubbed_languages = [language for language in normalized_languages if is_spanish_language(language)]
                spanish_auto_confirmed = has_spanish_auto_dub(auto_dubbed_languages)
                safe_dub_kind = dub_kind if dub_kind in {"none", "manual", "automatic"} else None
                if safe_dub_kind is None:
                    safe_dub_kind = "manual" if safe_has_dubbing else "none"
                if safe_has_dubbing and spanish_auto_confirmed:
                    safe_dub_kind = "automatic"
                elif safe_dub_kind == "automatic":
                    safe_dub_kind = "manual" if safe_has_dubbing else "none"
                safe_dub_kind = effective_dub_kind(safe_dub_kind, normalized_languages)
                final_published_year = published_year(published_at)
                final_view_count_sort = view_count if view_count is not None else None
                confidence = dub_confidence
                if confidence not in {"high", "medium", "low"}:
                    confidence = "high" if safe_dub_kind in {"none", "automatic"} else "low"
                evidence_json = json.dumps(evidence_dict)
                safe_title, safe_channel, safe_channel_id = sanitize_inspection_metadata(
                    video_id,
                    title,
                    channel,
                    channel_id,
                )
                checked_at = to_iso()
                conn.execute(
                    """
                    UPDATE videos
                    SET has_dubbing = ?,
                        audio_languages_json = ?,
                        audio_language_count = ?,
                        dub_kind = ?,
                        dub_confidence = ?,
                        dub_evidence_json = ?,
                        dub_classifier_version = ?,
                        title = COALESCE(NULLIF(?, ''), title),
                        channel = COALESCE(NULLIF(?, ''), channel),
                        channel_id = COALESCE(NULLIF(?, ''), channel_id),
                        duration_seconds = COALESCE(?, duration_seconds),
                        thumbnail_url = COALESCE(NULLIF(?, ''), thumbnail_url),
                        published_at = COALESCE(?, published_at),
                        view_count = COALESCE(?, view_count),
                        published_year = COALESCE(?, published_year),
                        view_count_sort = COALESCE(?, view_count_sort),
                        catalog_visible = CASE
                            WHEN COALESCE(?, published_at) IS NOT NULL AND COALESCE(?, published_at) != '' THEN 1
                            ELSE 0
                        END,
                        metadata_complete = CASE
                            WHEN COALESCE(?, published_at) IS NOT NULL AND COALESCE(?, published_at) != ''
                             AND COALESCE(?, view_count) IS NOT NULL
                             AND COALESCE(NULLIF(?, ''), title) != video_id
                             AND COALESCE(NULLIF(?, ''), channel) IS NOT NULL
                             AND COALESCE(NULLIF(?, ''), channel) != ''
                             AND COALESCE(NULLIF(?, ''), channel) != COALESCE(NULLIF(?, ''), title)
                             AND COALESCE(NULLIF(?, ''), channel) != video_id THEN 1
                            ELSE 0
                        END,
                        metadata_sort_at = ?,
                        last_checked_at = ?,
                        inspect_status = 'ok',
                        inspect_error = NULL
                    WHERE video_id = ?
                    """,
                    (
                        1 if safe_has_dubbing else 0,
                        json.dumps(normalized_languages),
                        len(normalized_languages),
                        safe_dub_kind,
                        confidence,
                        evidence_json,
                        classifier_version,
                        safe_title,
                        safe_channel,
                        safe_channel_id,
                        duration_seconds,
                        thumbnail_url,
                        published_at,
                        view_count,
                        final_published_year,
                        final_view_count_sort,
                        published_at,
                        published_at,
                        published_at,
                        published_at,
                        view_count,
                        safe_title,
                        safe_channel,
                        safe_channel,
                        safe_channel,
                        safe_title,
                        safe_channel,
                        checked_at,
                        checked_at,
                        video_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE candidate_frontier
                    SET title = COALESCE(NULLIF(?, ''), title),
                        channel = COALESCE(NULLIF(?, ''), channel),
                        channel_id = COALESCE(NULLIF(?, ''), channel_id),
                        duration_seconds = COALESCE(?, duration_seconds),
                        thumbnail_url = COALESCE(NULLIF(?, ''), thumbnail_url),
                        published_at = COALESCE(?, published_at),
                        view_count = COALESCE(?, view_count),
                        updated_at = ?
                    WHERE video_id = ?
                    """,
                    (
                        safe_title,
                        safe_channel,
                        safe_channel_id,
                        duration_seconds,
                        thumbnail_url,
                        published_at,
                        view_count,
                        checked_at,
                        video_id,
                    ),
                )
                self._replace_audio_tracks(
                    conn,
                    video_id,
                    normalized_languages,
                    is_auto_dubbed=None,
                    auto_dubbed_languages=auto_dubbed_languages,
                    original_audio_languages=original_audio_languages,
                    evidence_source=str(evidence_dict.get("source") or "inspection"),
                )
                self._refresh_video_metadata_complete(conn, video_id)
                self._sync_video_search(conn, video_id)

    def store_inspection_failures_batch(self, failures: list[tuple[str, str]]) -> None:
        if not failures:
            return
        timestamp = to_iso()
        with self.db.connect() as conn:
            for video_id, error in failures:
                conn.execute(
                    """
                    UPDATE videos
                    SET last_checked_at = ?,
                        catalog_visible = 0,
                        metadata_sort_at = ?,
                        inspect_status = 'failed',
                        inspect_error = ?
                    WHERE video_id = ?
                    """,
                    (timestamp, timestamp, error[:500], video_id),
                )

    def _fts_query(self, query: str) -> str:
        cleaned = " ".join(str(query or "").strip().split())
        return f'"{cleaned.replace(chr(34), chr(34) + chr(34))}"'

    def _catalog_search_mode(self, conn: Any, query: str | None) -> str:
        cleaned = " ".join(str(query or "").strip().split())
        if not cleaned:
            return "none"
        if len(cleaned) < 3:
            return "like"

        rows = conn.execute(
            "SELECT rowid FROM video_search WHERE video_search MATCH ? LIMIT ?",
            (self._fts_query(cleaned), CATALOG_SEARCH_PROBE_LIMIT),
        ).fetchall()
        if not rows:
            return "none"
        if len(rows) >= CATALOG_SEARCH_PROBE_LIMIT:
            first_rowid = int(rows[0][0])
            last_rowid = int(rows[-1][0])
            span = max(1, last_rowid - first_rowid + 1)
            density = len(rows) / span
            if density >= CATALOG_SEARCH_DENSE_MATCH_RATIO:
                return "like"
        return "fts"

    def _catalog_clauses(
        self,
        *,
        lang: str | None,
        source_id: int | None,
        channel: str | None,
        query: str | None,
        only_dubbed: bool,
        only_favorites: bool = False,
        dub_kind: str | None = None,
        sort_by: str = "recent",
        year: int | None = None,
        year_after: int | None = None,
        year_before: int | None = None,
        query_mode: str = "legacy",
    ) -> tuple[list[str], list[Any]]:
        clauses = [
            "v.catalog_visible = 1",
            "v.metadata_complete = 1",
            "NOT (LENGTH(TRIM(COALESCE(v.title, ''))) = 11 "
            "AND TRIM(COALESCE(v.title, '')) NOT GLOB '*[^A-Za-z0-9_-]*')",
            "NOT (TRIM(COALESCE(v.title, '')) != '' "
            "AND TRIM(COALESCE(v.channel, '')) = TRIM(COALESCE(v.title, '')))",
            "v.published_at IS NOT NULL",
            "v.published_at != ''",
        ]
        params: list[Any] = []

        if only_dubbed:
            clauses.append("v.has_dubbing = 1")
        if only_favorites:
            clauses.append("v.is_favorite = 1")
        if lang:
            if lang == SPANISH_LANGUAGE_FILTER:
                clauses.append(
                    "EXISTS (SELECT 1 FROM video_audio_tracks t "
                    "WHERE t.video_id = v.video_id AND t.language_base = 'es' AND t.is_original_audio = 0)"
                )
            else:
                clauses.append(
                    "EXISTS (SELECT 1 FROM video_audio_tracks t "
                    "WHERE t.video_id = v.video_id AND t.language_code = ? AND t.is_original_audio = 0)"
                )
                params.append(lang)
        if channel:
            clauses.append("v.channel = ?")
            params.append(channel)
        if query:
            lowered_query = f"%{query.lower()}%"
            if query_mode == "like":
                clauses.append("(LOWER(v.title) LIKE ? OR LOWER(COALESCE(v.channel, '')) LIKE ?)")
                params.extend([lowered_query, lowered_query])
            elif query_mode == "fts":
                clauses.append("v.rowid IN (SELECT rowid FROM video_search WHERE video_search MATCH ?)")
                params.append(self._fts_query(query))
            else:
                clauses.append(
                    "("
                    "v.rowid IN (SELECT rowid FROM video_search WHERE video_search MATCH ?) "
                    "OR LOWER(v.title) LIKE ? "
                    "OR LOWER(COALESCE(v.channel, '')) LIKE ?"
                    ")"
                )
                params.extend([self._fts_query(query), lowered_query, lowered_query])
        if source_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM video_sources vs WHERE vs.video_id = v.video_id AND vs.source_id = ?)"
            )
            params.append(source_id)
        if dub_kind == "automatic":
            if lang == SPANISH_LANGUAGE_FILTER or not lang:
                clauses.append(
                    "EXISTS (SELECT 1 FROM video_audio_tracks t "
                    "WHERE t.video_id = v.video_id AND t.language_base = 'es' "
                    "AND t.is_auto_dubbed = 1 AND t.is_original_audio = 0)"
                )
            else:
                clauses.append(
                    "EXISTS (SELECT 1 FROM video_audio_tracks t "
                    "WHERE t.video_id = v.video_id AND t.language_code = ? "
                    "AND t.is_auto_dubbed = 1 AND t.is_original_audio = 0)"
                )
                params.append(lang)
        elif dub_kind == "manual":
            clauses.append(
                "("
                "COALESCE(v.dub_classifier_version, 0) >= ? "
                "OR (COALESCE(v.dub_evidence_json, '') NOT LIKE ? "
                "AND COALESCE(v.dub_evidence_json, '') NOT LIKE ?)"
                ")"
            )
            params.extend(
                [
                    CURRENT_DUB_CLASSIFIER_VERSION,
                    '%"source":"yt_dlp"%',
                    '%"source": "yt_dlp"%',
                ]
            )
            if lang == SPANISH_LANGUAGE_FILTER or not lang:
                clauses.append(
                    "EXISTS (SELECT 1 FROM video_audio_tracks t "
                    "WHERE t.video_id = v.video_id AND t.language_base = 'es' "
                    "AND COALESCE(t.is_auto_dubbed, 0) != 1 AND t.is_original_audio = 0)"
                )
            else:
                clauses.append(
                    "EXISTS (SELECT 1 FROM video_audio_tracks t "
                    "WHERE t.video_id = v.video_id AND t.language_code = ? "
                    "AND COALESCE(t.is_auto_dubbed, 0) != 1 AND t.is_original_audio = 0)"
                )
                params.append(lang)
        if year is not None:
            clauses.append("v.published_year = ?")
            params.append(year)
        if year_after is not None:
            clauses.append("v.published_year >= ?")
            params.append(year_after)
        if year_before is not None:
            clauses.append("v.published_year <= ?")
            params.append(year_before)
        return clauses, params

    def count_catalog(
        self,
        *,
        lang: str | None,
        source_id: int | None,
        channel: str | None,
        query: str | None,
        only_dubbed: bool,
        only_favorites: bool = False,
        dub_kind: str | None = None,
        year: int | None = None,
        year_after: int | None = None,
        year_before: int | None = None,
    ) -> int:
        with self.db.connect() as conn:
            search_mode = self._catalog_search_mode(conn, query) if query else "legacy"
            if search_mode == "none":
                return 0
            effective_query = query if search_mode in {"like", "fts"} else query
            clauses, params = self._catalog_clauses(
                lang=lang,
                source_id=source_id,
                channel=channel,
                query=effective_query,
                only_dubbed=only_dubbed,
                only_favorites=only_favorites,
                dub_kind=dub_kind,
                year=year,
                year_after=year_after,
                year_before=year_before,
                query_mode=search_mode,
            )
            sql = f"SELECT COUNT(*) FROM videos v WHERE {' AND '.join(clauses)}"
            return int(conn.execute(sql, params).fetchone()[0])

    def list_catalog_page(
        self,
        *,
        lang: str | None,
        source_id: int | None,
        channel: str | None,
        query: str | None,
        only_dubbed: bool,
        only_favorites: bool = False,
        dub_kind: str | None = None,
        sort_by: str = "recent",
        year: int | None = None,
        year_after: int | None = None,
        year_before: int | None = None,
        page_size: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        cursor_payload = decode_cursor(cursor)
        sort_key = sort_by if sort_by in {"recent", "oldest", "views", "random"} else "recent"
        safe_page_size = max(1, min(500, int(page_size)))
        order_by_map = {
            "recent": "v.published_at DESC, v.last_seen_at DESC, v.video_id DESC",
            "oldest": "v.published_at ASC, v.last_seen_at ASC, v.video_id ASC",
            "views": "v.view_count_sort DESC, v.published_at DESC, v.video_id DESC",
            "random": "v.random_key ASC, v.video_id ASC",
        }

        with self.db.connect() as conn:
            search_mode = self._catalog_search_mode(conn, query) if query else "legacy"
            if search_mode == "none":
                return {"items": [], "next_cursor": None, "total_estimate": None}

            clauses, params = self._catalog_clauses(
                lang=lang,
                source_id=source_id,
                channel=channel,
                query=query if search_mode == "like" else None,
                only_dubbed=only_dubbed,
                only_favorites=only_favorites,
                dub_kind=dub_kind,
                year=year,
                year_after=year_after,
                year_before=year_before,
                query_mode=search_mode,
            )

            from_clause = "videos v"
            if search_mode == "fts":
                from_clause = "video_search s CROSS JOIN videos v ON v.rowid = s.rowid"
                clauses.insert(0, "video_search MATCH ?")
                params.insert(0, self._fts_query(query or ""))

            if cursor_payload and cursor_payload.get("sort") == sort_key:
                if sort_key == "recent":
                    clauses.append(
                        "(v.published_at < ? OR (v.published_at = ? AND v.last_seen_at < ?) OR "
                        "(v.published_at = ? AND v.last_seen_at = ? AND v.video_id < ?))"
                    )
                    params.extend([
                        cursor_payload["published_at"],
                        cursor_payload["published_at"],
                        cursor_payload["last_seen_at"],
                        cursor_payload["published_at"],
                        cursor_payload["last_seen_at"],
                        cursor_payload["video_id"],
                    ])
                elif sort_key == "oldest":
                    clauses.append(
                        "(v.published_at > ? OR (v.published_at = ? AND v.last_seen_at > ?) OR "
                        "(v.published_at = ? AND v.last_seen_at = ? AND v.video_id > ?))"
                    )
                    params.extend([
                        cursor_payload["published_at"],
                        cursor_payload["published_at"],
                        cursor_payload["last_seen_at"],
                        cursor_payload["published_at"],
                        cursor_payload["last_seen_at"],
                        cursor_payload["video_id"],
                    ])
                elif sort_key == "views":
                    clauses.append(
                        "(v.view_count_sort < ? OR (v.view_count_sort = ? AND v.published_at < ?) OR "
                        "(v.view_count_sort = ? AND v.published_at = ? AND v.video_id < ?))"
                    )
                    params.extend([
                        cursor_payload["view_count_sort"],
                        cursor_payload["view_count_sort"],
                        cursor_payload["published_at"],
                        cursor_payload["view_count_sort"],
                        cursor_payload["published_at"],
                        cursor_payload["video_id"],
                    ])
                elif sort_key == "random":
                    clauses.append("(v.random_key > ? OR (v.random_key = ? AND v.video_id > ?))")
                    params.extend([
                        cursor_payload["random_key"],
                        cursor_payload["random_key"],
                        cursor_payload["video_id"],
                    ])

            params_with_limit = [*params, safe_page_size + 1]
            page_sql = f"""
                SELECT v.video_id, v.published_at, v.last_seen_at, v.view_count_sort, v.random_key
                FROM {from_clause}
                WHERE {' AND '.join(clauses)}
                ORDER BY {order_by_map[sort_key]}
                LIMIT ?
            """
            page_rows = conn.execute(page_sql, params_with_limit).fetchall()
            has_more = len(page_rows) > safe_page_size
            page_rows = page_rows[:safe_page_size]
            video_ids = [str(row["video_id"]) for row in page_rows]
            if not video_ids:
                return {"items": [], "next_cursor": None, "total_estimate": None}

            placeholders = ",".join("?" for _ in video_ids)
            detail_rows = conn.execute(
                f"SELECT * FROM videos WHERE video_id IN ({placeholders})",
                video_ids,
            ).fetchall()
            source_rows = conn.execute(
                f"""
                SELECT vs.video_id, GROUP_CONCAT(DISTINCT s.label) AS source_labels
                FROM video_sources vs
                JOIN sources s ON s.id = vs.source_id
                WHERE vs.video_id IN ({placeholders})
                GROUP BY vs.video_id
                """,
                video_ids,
            ).fetchall()
            track_rows = conn.execute(
                f"""
                SELECT video_id, language_code
                FROM video_audio_tracks
                WHERE video_id IN ({placeholders})
                ORDER BY language_code
                """,
                video_ids,
            ).fetchall()

        by_id = {str(row["video_id"]): dict(row) for row in detail_rows}
        source_labels = {str(row["video_id"]): row["source_labels"] for row in source_rows}
        languages_by_id: dict[str, list[str]] = {}
        for row in track_rows:
            languages_by_id.setdefault(str(row["video_id"]), []).append(str(row["language_code"]))

        items: list[dict[str, Any]] = []
        for page_row in page_rows:
            video_id = str(page_row["video_id"])
            payload = by_id.get(video_id)
            if not payload:
                continue
            payload["source_labels"] = source_labels.get(video_id, "")
            languages = normalize_audio_languages(languages_by_id.get(video_id, []))
            if not languages:
                languages = normalize_audio_languages(json.loads(payload["audio_languages_json"] or "[]"))
            payload["audio_languages"] = languages
            payload["dub_kind"] = effective_dub_kind_from_normalized(str(payload.get("dub_kind") or ""), languages)
            payload["upload_year"] = payload.get("published_year") or published_year(str(payload.get("published_at") or ""))
            items.append(payload)

        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_cursor(
                {
                    "sort": sort_key,
                    "video_id": str(last["video_id"]),
                    "published_at": str(last["published_at"] or ""),
                    "last_seen_at": str(last["last_seen_at"] or ""),
                    "view_count_sort": int(last["view_count_sort"] or -1),
                    "random_key": float(last["random_key"] or 0),
                }
            )
        return {"items": items, "next_cursor": next_cursor, "total_estimate": None}

    def list_catalog(
        self,
        *,
        lang: str | None,
        source_id: int | None,
        channel: str | None,
        query: str | None,
        only_dubbed: bool,
        only_favorites: bool = False,
        dub_kind: str | None = None,
        sort_by: str = "recent",
        year: int | None = None,
        year_after: int | None = None,
        year_before: int | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = self.list_catalog_page(
                lang=lang,
                source_id=source_id,
                channel=channel,
                query=query,
                only_dubbed=only_dubbed,
                only_favorites=only_favorites,
                dub_kind=dub_kind,
                sort_by=sort_by,
                year=year,
                year_after=year_after,
                year_before=year_before,
                page_size=500,
                cursor=cursor,
            )
            items.extend(page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
            if len(items) >= 100000:
                break
        return items

    def list_catalog_filters(self) -> dict[str, list[Any]]:
        with self.db.connect() as conn:
            channels = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT DISTINCT channel
                    FROM videos
                    WHERE catalog_visible = 1
                      AND channel IS NOT NULL
                      AND channel != ''
                    ORDER BY channel COLLATE NOCASE
                    """
                ).fetchall()
            ]
            languages = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT DISTINCT t.language_code
                    FROM video_audio_tracks t
                    JOIN videos v ON v.video_id = t.video_id
                    WHERE v.catalog_visible = 1
                      AND t.is_original_audio = 0
                    ORDER BY t.language_code
                    """
                ).fetchall()
            ]
            languages = normalize_audio_languages(languages)
            has_spanish = any(audio_language_base(lang) == "es" for lang in languages)
            grouped_languages = [lang for lang in languages if audio_language_base(lang) != "es"]
            if has_spanish:
                grouped_languages.insert(0, SPANISH_LANGUAGE_FILTER)
            languages = grouped_languages
            years = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT DISTINCT published_year AS upload_year
                    FROM videos
                    WHERE catalog_visible = 1
                      AND published_year IS NOT NULL
                    ORDER BY upload_year DESC
                    """
                ).fetchall()
                if row[0]
            ]
        return {"channels": channels, "languages": languages, "years": years}

    def enqueue_job(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        priority: int = 100,
        not_before: str | None = None,
        run_id: int | None = None,
    ) -> int:
        timestamp = to_iso()
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scheduler_jobs(
                    job_type, state, priority, not_before, attempts, run_id,
                    payload_json, idempotency_key, created_at, updated_at
                )
                VALUES (?, 'queued', ?, ?, 0, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    priority = MIN(priority, excluded.priority),
                    not_before = MIN(not_before, excluded.not_before),
                    updated_at = excluded.updated_at
                RETURNING id
                """,
                (
                    job_type,
                    int(priority),
                    not_before or timestamp,
                    run_id,
                    json.dumps(payload),
                    idempotency_key,
                    timestamp,
                    timestamp,
                ),
            )
            return int(cursor.fetchone()["id"])

    def claim_jobs(self, *, owner: str, limit: int = 10, lease_seconds: int = 300) -> list[dict[str, Any]]:
        timestamp = to_iso()
        lease_until = to_iso(utc_now() + timedelta(seconds=max(30, int(lease_seconds))))
        safe_limit = max(1, min(100, int(limit)))
        with self.db.connect() as conn:
            stale_rows = conn.execute(
                """
                SELECT id FROM scheduler_jobs
                WHERE state = 'leased' AND lease_expires_at < ?
                LIMIT ?
                """,
                (timestamp, safe_limit),
            ).fetchall()
            stale_ids = [int(row["id"]) for row in stale_rows]
            if stale_ids:
                placeholders = ",".join("?" for _ in stale_ids)
                conn.execute(
                    f"""
                    UPDATE scheduler_jobs
                    SET state = 'queued', lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    (timestamp, *stale_ids),
                )
            rows = conn.execute(
                """
                SELECT *
                FROM scheduler_jobs
                WHERE state = 'queued' AND not_before <= ?
                ORDER BY priority ASC, id ASC
                LIMIT ?
                """,
                (timestamp, safe_limit),
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"""
                    UPDATE scheduler_jobs
                    SET state = 'leased',
                        lease_owner = ?,
                        lease_expires_at = ?,
                        attempts = attempts + 1,
                        updated_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    (owner, lease_until, timestamp, *ids),
                )
        jobs = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = json.loads(payload.get("payload_json") or "{}")
            jobs.append(payload)
        return jobs

    def finish_job(self, job_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE scheduler_jobs
                SET state = 'done', lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE id = ?
                """,
                (to_iso(), job_id),
            )

    def fail_job(self, job_id: int, error: str, *, retry_at: str | None = None) -> None:
        with self.db.connect() as conn:
            if retry_at:
                conn.execute(
                    """
                    UPDATE scheduler_jobs
                    SET state = 'queued', not_before = ?, lease_owner = NULL, lease_expires_at = NULL,
                        last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (retry_at, error[:500], to_iso(), job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE scheduler_jobs
                    SET state = 'failed', lease_owner = NULL, lease_expires_at = NULL,
                        last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (error[:500], to_iso(), job_id),
                )

    def recover_scheduler_jobs(self) -> None:
        timestamp = to_iso()
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE scheduler_jobs
                SET state = 'queued', lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE state = 'leased' AND lease_expires_at < ?
                """,
                (timestamp, timestamp),
            )
            conn.execute(
                """
                UPDATE scrape_runs
                SET status = 'failed',
                    finished_at = ?,
                    error = COALESCE(error, 'Interrumpido al cerrar la app.')
                WHERE status = 'running'
                """,
                (timestamp,),
            )
