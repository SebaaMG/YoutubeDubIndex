from __future__ import annotations

import importlib
import base64
import json
import os
import re
import shutil
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any

from .config import Settings
from .repository import (
    audio_language_base,
    normalize_audio_language,
    normalize_audio_languages,
)


def ensure_yt_dlp_import(settings: Settings) -> Any:
    try:
        return importlib.import_module("yt_dlp")
    except ModuleNotFoundError:
        vendored = str(settings.vendored_deps_dir)
        if vendored not in sys.path and settings.vendored_deps_dir.exists():
            sys.path.insert(0, vendored)
        return importlib.import_module("yt_dlp")


@dataclass
class StartupDiagnostics:
    node_ok: bool
    ytdlp_ok: bool
    messages: list[str]

    @property
    def ok(self) -> bool:
        return self.ytdlp_ok


@dataclass
class InspectionResult:
    audio_languages: list[str]
    published_at: str | None = None
    view_count: int | None = None
    dub_kind: str | None = None
    auto_dubbed_languages: list[str] = field(default_factory=list)
    original_audio_languages: list[str] = field(default_factory=list)
    dub_confidence: str | None = None
    dub_evidence: dict[str, Any] | None = None
    title: str | None = None
    channel: str | None = None
    channel_id: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None

    def __post_init__(self) -> None:
        self.audio_languages = normalize_audio_languages(self.audio_languages)
        self.auto_dubbed_languages = normalize_audio_languages(self.auto_dubbed_languages)
        self.original_audio_languages = normalize_audio_languages(self.original_audio_languages)
        if self.dub_kind not in {"none", "manual", "automatic"}:
            self.dub_kind = "automatic" if self.has_dubbing and self.auto_dubbed_languages else "manual" if self.has_dubbing else "none"
        if self.dub_confidence not in {"high", "medium", "low"}:
            self.dub_confidence = "high" if self.dub_kind == "automatic" else "low"
        if self.dub_evidence is None:
            self.dub_evidence = {
                "source": "inspection",
                "auto_dubbed_languages": self.auto_dubbed_languages,
                "original_audio_languages": self.original_audio_languages,
                "languages": self.audio_languages,
            }

    @property
    def has_dubbing(self) -> bool:
        return len(self.audio_languages) > 1


class YouTubeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.node_path = self.resolve_node_path()
        if self.node_path:
            os.environ["PATH"] = str(self.node_path.parent) + os.pathsep + os.environ.get("PATH", "")
        self._yt_dlp = ensure_yt_dlp_import(settings)

    @property
    def base_opts(self) -> dict[str, Any]:
        return {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 12,
            "extractor_retries": 1,
            "retries": 1,
            "file_access_retries": 1,
            "extract_flat": False,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": ["web_embedded", "web"]}},
        }

    def startup_diagnostics(self) -> StartupDiagnostics:
        messages: list[str] = []
        node_ok = self.node_path is not None
        if node_ok:
            messages.append(f"Node runtime: {self.node_path}")
        else:
            messages.append(
                "Node.js no esta disponible. La extraccion rapida puede ser menos estable, "
                "pero la app aun puede funcionar."
            )
        messages.append("Extraccion de YouTube lista; la validacion real se hara al revisar videos.")

        return StartupDiagnostics(node_ok=node_ok, ytdlp_ok=True, messages=messages)

    def discover_source(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        source_type = source["type"]
        max_candidates = int(source["max_candidates_per_run"])
        opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 12,
            "extractor_retries": 1,
            "retries": 1,
            "file_access_retries": 1,
            "extract_flat": True,
            "playlistend": max_candidates,
        }

        if source_type == "search":
            target = f'ytsearch{max_candidates}:{source["value"]}'
        elif source_type == "channel":
            target = self.normalize_channel_value(source["value"])
        else:
            raise ValueError(f"Tipo de fuente no soportado: {source_type}")

        with self._yt_dlp.YoutubeDL(opts) as ydl:
            payload = ydl.extract_info(target, download=False)

        entries = payload.get("entries") or []
        return [self._candidate_from_entry(entry) for entry in entries if entry and entry.get("id")]

    def inspect_video(self, video_id: str) -> InspectionResult:
        try:
            html = self.fetch_watch_page(video_id)
            payload = self.extract_player_response(html)
        except Exception:
            return self.inspect_video_with_ytdlp(video_id)

        published_at = self.extract_published_at(payload)
        if published_at is None:
            published_at = self.extract_published_at_from_html(html)
        view_count = self.extract_view_count(payload)
        if view_count is None:
            view_count = self.extract_view_count_from_html(html)
        audio_languages = self.extract_audio_tracks_from_payload(payload)
        original_audio_languages = self.extract_original_audio_languages_from_payload(payload)
        metadata = self.extract_video_metadata_from_payload(payload)
        info: dict[str, Any] | None = None
        if (
            published_at is None
            or view_count is None
            or not metadata.get("channel")
            or self.metadata_needs_ytdlp(video_id, metadata)
        ):
            try:
                info = self.extract_video_info(video_id)
            except Exception:
                info = None
            if info:
                if published_at is None:
                    published_at = self.extract_published_at_from_info(info)
                if view_count is None:
                    view_count = self.extract_view_count_from_info(info)
                if not audio_languages:
                    audio_languages = self.extract_audio_languages(info)
                if not original_audio_languages:
                    original_audio_languages = self.extract_original_audio_languages_from_info(info)
                metadata = self.merge_video_metadata(
                    metadata,
                    self.extract_video_metadata_from_info(info),
                    video_id=video_id,
                )
        auto_dubbed_languages = self.merge_audio_languages(
            self.extract_auto_dubbed_languages_from_payload(payload),
            self.extract_auto_dubbed_languages_from_info(info or {}),
        )
        normalized_audio_languages = normalize_audio_languages(audio_languages)
        spanish_non_original_inferred = (
            len(normalized_audio_languages) > 1
            and not original_audio_languages
            and any(self.is_spanish_language(language) for language in normalized_audio_languages)
        )
        return InspectionResult(
            audio_languages=audio_languages,
            published_at=published_at,
            view_count=view_count,
            dub_kind="automatic" if auto_dubbed_languages else self.classify_dub_kind(audio_languages, html, payload, info),
            auto_dubbed_languages=auto_dubbed_languages,
            original_audio_languages=original_audio_languages,
            dub_confidence="high" if auto_dubbed_languages else "low",
            dub_evidence={
                "source": "inspection",
                "auto_dubbed_languages": auto_dubbed_languages,
                "original_audio_languages": original_audio_languages,
                "languages": normalized_audio_languages,
                "spanish_non_original_inferred": spanish_non_original_inferred,
            },
            **metadata,
        )

    def inspect_video_with_ytdlp(self, video_id: str) -> InspectionResult:
        info = self.extract_video_info(video_id)
        audio_languages = self.extract_audio_languages(info)
        auto_dubbed_languages = self.extract_auto_dubbed_languages_from_info(info)
        original_audio_languages = self.extract_original_audio_languages_from_info(info)
        return InspectionResult(
            audio_languages=audio_languages,
            published_at=self.extract_published_at_from_info(info),
            view_count=self.extract_view_count_from_info(info),
            dub_kind="automatic" if auto_dubbed_languages else self.classify_dub_kind(audio_languages, "", {}, info),
            auto_dubbed_languages=auto_dubbed_languages,
            original_audio_languages=original_audio_languages,
            dub_confidence="high" if auto_dubbed_languages else "low",
            dub_evidence={
                "source": "yt_dlp",
                "auto_dubbed_languages": auto_dubbed_languages,
                "original_audio_languages": original_audio_languages,
                "languages": normalize_audio_languages(audio_languages),
            },
            **self.extract_video_metadata_from_info(info),
        )

    def extract_video_info(self, video_id: str) -> dict[str, Any]:
        with self._yt_dlp.YoutubeDL(self.base_opts) as ydl:
            return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

    @staticmethod
    def extract_audio_languages(info: dict[str, Any]) -> list[str]:
        formats = info.get("formats") or []
        languages = normalize_audio_languages(
            [
                fmt.get("language")
                for fmt in formats
                if fmt.get("language") and fmt.get("acodec") != "none" and fmt.get("vcodec") == "none"
            ]
        )
        if not languages and info.get("language"):
            languages = normalize_audio_languages([info["language"]])
        return languages

    @staticmethod
    def is_spanish_language(value: Any) -> bool:
        language = normalize_audio_language(value)
        return bool(language and audio_language_base(language) == "es")

    @classmethod
    def merge_audio_languages(cls, *groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            merged.extend(group)
        return normalize_audio_languages(merged)

    @staticmethod
    def fetch_watch_page(video_id: str) -> str:
        request = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}&hl=en",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")

    @classmethod
    def extract_audio_tracks_from_watch_html(cls, html: str) -> list[str]:
        payload = cls.extract_player_response(html)
        return cls.extract_audio_tracks_from_payload(payload)

    @classmethod
    def extract_audio_tracks_from_payload(cls, payload: dict[str, Any]) -> list[str]:
        captions = payload.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
        tracks = captions.get("audioTracks") or []

        languages: list[str] = []
        seen: set[str] = set()
        for index, track in enumerate(tracks):
            raw_track_id = track.get("audioTrackId") or ""
            lang = normalize_audio_language(
                raw_track_id.split(".", 1)[0] if raw_track_id else ""
            )
            if lang and lang not in seen:
                seen.add(lang)
                languages.append(lang)

        default_lang = payload.get("language")
        if not languages and default_lang:
            languages = [default_lang]
        return normalize_audio_languages(languages)

    @classmethod
    def extract_original_audio_languages_from_payload(cls, payload: dict[str, Any]) -> list[str]:
        languages: list[str] = []
        captions = payload.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
        for track in captions.get("audioTracks") or []:
            if not isinstance(track, dict) or not cls.audio_track_has_original_marker(track):
                continue
            language = cls.language_from_audio_track(track)
            if language:
                languages.append(str(language))

        streaming_data = payload.get("streamingData") or {}
        if isinstance(streaming_data, dict):
            for group in ("formats", "adaptiveFormats"):
                for fmt in streaming_data.get(group) or []:
                    if not isinstance(fmt, dict) or not cls.format_is_original(fmt):
                        continue
                    language = cls.language_from_format(fmt)
                    if language:
                        languages.append(str(language))
        return normalize_audio_languages(languages)

    @classmethod
    def extract_auto_dubbed_languages_from_payload(cls, payload: dict[str, Any]) -> list[str]:
        languages: list[str] = []
        captions = payload.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
        for track in captions.get("audioTracks") or []:
            if not isinstance(track, dict) or not cls.audio_track_has_auto_dub_marker(track):
                continue
            language = cls.language_from_audio_track(track)
            if cls.is_spanish_language(language):
                languages.append(str(language))

        streaming_data = payload.get("streamingData") or {}
        if isinstance(streaming_data, dict):
            for group in ("formats", "adaptiveFormats"):
                for fmt in streaming_data.get(group) or []:
                    if not isinstance(fmt, dict) or not cls.format_has_auto_dub_marker(fmt):
                        continue
                    language = cls.language_from_format(fmt)
                    if cls.is_spanish_language(language):
                        languages.append(str(language))
        return normalize_audio_languages(languages)

    @classmethod
    def extract_auto_dubbed_languages_from_info(cls, info: dict[str, Any]) -> list[str]:
        languages: list[str] = []
        for fmt in info.get("formats") or []:
            if not isinstance(fmt, dict) or not cls.format_has_auto_dub_marker(fmt):
                continue
            language = cls.language_from_format(fmt)
            if cls.is_spanish_language(language):
                languages.append(str(language))
        return normalize_audio_languages(languages)

    @classmethod
    def extract_original_audio_languages_from_info(cls, info: dict[str, Any]) -> list[str]:
        audio_formats = [
            fmt for fmt in info.get("formats") or []
            if isinstance(fmt, dict) and cls.format_is_audio_only(fmt)
        ]
        languages = cls.extract_original_audio_languages_from_formats(audio_formats)
        if not languages and info.get("language"):
            languages = normalize_audio_languages([str(info["language"])])
        return languages

    @classmethod
    def classify_dub_kind(
        cls,
        audio_languages: list[str],
        html: str,
        payload: dict[str, Any],
        info: dict[str, Any] | None = None,
    ) -> str:
        languages = normalize_audio_languages(audio_languages)
        if len(languages) <= 1:
            return "none"
        if cls.has_auto_dubbed_marker(html, payload, info):
            return "automatic"
        return "manual"

    @classmethod
    def merge_video_metadata(
        cls,
        primary: dict[str, Any],
        fallback: dict[str, Any],
        *,
        video_id: str | None = None,
    ) -> dict[str, Any]:
        merged = dict(primary)
        for key, value in fallback.items():
            if value is None:
                continue
            if key == "title" and cls.metadata_text_is_invalid_title(merged.get(key), video_id):
                merged[key] = value
                continue
            if key == "channel" and cls.metadata_text_is_invalid_channel(
                merged.get(key),
                video_id,
                merged.get("title"),
                fallback.get("title"),
            ):
                merged[key] = value
                continue
            if not merged.get(key):
                merged[key] = value
        return merged

    @staticmethod
    def metadata_text_is_invalid_title(value: Any, video_id: str | None = None) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        if video_id and text == video_id:
            return True
        return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", text))

    @classmethod
    def metadata_text_is_invalid_channel(
        cls,
        value: Any,
        video_id: str | None = None,
        current_title: Any = None,
        fallback_title: Any = None,
    ) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        if video_id and text == video_id:
            return True
        title_text = str(current_title or "").strip()
        fallback_title_text = str(fallback_title or "").strip()
        if title_text and text == title_text:
            return True
        if fallback_title_text and text == fallback_title_text:
            return True
        return False

    @classmethod
    def metadata_needs_ytdlp(cls, video_id: str, metadata: dict[str, Any]) -> bool:
        return cls.metadata_text_is_invalid_title(metadata.get("title"), video_id) or cls.metadata_text_is_invalid_channel(
            metadata.get("channel"),
            video_id,
            metadata.get("title"),
        )

    @staticmethod
    def extract_video_metadata_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
        details = payload.get("videoDetails") or {}
        thumbnail = details.get("thumbnail") or {}
        thumbnails = thumbnail.get("thumbnails") or []
        duration = details.get("lengthSeconds")
        try:
            duration_seconds = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration_seconds = None
        return {
            "title": details.get("title"),
            "channel": details.get("author"),
            "channel_id": details.get("channelId"),
            "duration_seconds": duration_seconds,
            "thumbnail_url": thumbnails[-1].get("url") if thumbnails else None,
        }

    @staticmethod
    def extract_video_metadata_from_info(info: dict[str, Any]) -> dict[str, Any]:
        duration = info.get("duration")
        try:
            duration_seconds = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration_seconds = None
        return {
            "title": info.get("title"),
            "channel": info.get("channel") or info.get("uploader"),
            "channel_id": info.get("channel_id") or info.get("uploader_id"),
            "duration_seconds": duration_seconds,
            "thumbnail_url": info.get("thumbnail"),
        }

    @staticmethod
    def has_auto_dubbed_marker(
        html: str,
        payload: dict[str, Any] | None = None,
        info: dict[str, Any] | None = None,
    ) -> bool:
        del html
        if payload and YouTubeService.payload_has_auto_dubbed_audio_track(payload):
            return True
        return bool(info and YouTubeService.info_has_auto_dubbed_audio_track(info))

    @classmethod
    def payload_has_auto_dubbed_audio_track(cls, payload: dict[str, Any]) -> bool:
        return bool(cls.extract_auto_dubbed_languages_from_payload(payload))

    @classmethod
    def info_has_auto_dubbed_audio_track(cls, info: dict[str, Any]) -> bool:
        return bool(cls.extract_auto_dubbed_languages_from_info(info))

    @classmethod
    def format_has_auto_dub_marker(cls, fmt: dict[str, Any]) -> bool:
        if cls.audio_track_has_auto_dub_marker(fmt):
            return True
        for key in ("audioTrack", "audio_track"):
            audio_track = fmt.get(key)
            if isinstance(audio_track, dict) and cls.audio_track_has_auto_dub_marker(audio_track):
                return True
        if cls.contains_auto_dub_marker(fmt.get("xtags")):
            return True
        return any(
            cls.contains_auto_dub_marker(value)
            for value in cls.format_url_xtags(fmt)
        )

    @staticmethod
    def format_is_audio_only(fmt: dict[str, Any]) -> bool:
        return bool(fmt.get("acodec") and fmt.get("acodec") != "none" and fmt.get("vcodec") == "none")

    @staticmethod
    def format_url_xtags(fmt: dict[str, Any]) -> list[str]:
        url = str(fmt.get("url") or "")
        if not url:
            return []
        try:
            query = parse_qs(urlparse(url).query)
        except Exception:
            return []
        return [value for value in query.get("xtags", []) if value]

    @classmethod
    def format_is_original(cls, fmt: dict[str, Any]) -> bool:
        values = [
            fmt.get("format_note"),
            fmt.get("format"),
            fmt.get("displayName"),
            fmt.get("name"),
            fmt.get("label"),
        ]
        for key in ("audioTrack", "audio_track"):
            audio_track = fmt.get(key)
            if isinstance(audio_track, dict):
                values.extend(
                    [
                        audio_track.get("displayName"),
                        audio_track.get("name"),
                        audio_track.get("label"),
                        audio_track.get("format_note"),
                    ]
                )
        haystack = " ".join(str(value or "") for value in values).lower()
        if re.search(r"\boriginal\b", haystack):
            return True
        try:
            return int(fmt.get("language_preference")) >= 10
        except (TypeError, ValueError):
            return False

    @classmethod
    def extract_original_audio_languages_from_formats(cls, formats: list[dict[str, Any]]) -> list[str]:
        return normalize_audio_languages(
            [
                str(language)
                for fmt in formats
                for language in [cls.language_from_format(fmt)]
                if language and cls.format_is_original(fmt)
            ]
        )

    @classmethod
    def language_from_format(cls, fmt: dict[str, Any]) -> str | None:
        language = normalize_audio_language(fmt.get("language") or fmt.get("language_code"))
        if language:
            return language
        for key in ("audioTrack", "audio_track"):
            audio_track = fmt.get(key)
            if isinstance(audio_track, dict):
                language = cls.language_from_audio_track(audio_track)
                if language:
                    return language
        return cls.language_from_audio_track(fmt)

    @staticmethod
    def language_from_audio_track(track: dict[str, Any]) -> str | None:
        raw = track.get("audioTrackId") or track.get("id") or track.get("language") or track.get("languageCode")
        if raw:
            return normalize_audio_language(str(raw).split(".", 1)[0])
        return None

    @classmethod
    def audio_track_has_auto_dub_marker(cls, track: dict[str, Any]) -> bool:
        for key in ("isAutoDubbed", "is_auto_dubbed", "auto_dubbed"):
            if track.get(key) is True:
                return True

        selected: dict[str, Any] = {}
        for key in ("audioTrackId", "id", "displayName", "name", "label", "format_note", "xtags"):
            value = track.get(key)
            if value is not None:
                selected[key] = value
        return cls.contains_auto_dub_marker(json.dumps(selected, ensure_ascii=False))

    @staticmethod
    def audio_track_has_original_marker(track: dict[str, Any]) -> bool:
        selected: dict[str, Any] = {}
        for key in ("audioTrackId", "id", "displayName", "name", "label", "format_note"):
            value = track.get(key)
            if value is not None:
                selected[key] = value
        haystack = json.dumps(selected, ensure_ascii=False).lower()
        return bool(re.search(r"\boriginal\b", haystack))

    @staticmethod
    def contains_auto_dub_marker(value: str | None) -> bool:
        original = value or ""
        text = original.lower()
        if not text:
            return False
        decoded_text = " ".join(YouTubeService.iter_decoded_xtag_texts(original)).lower()
        haystack = f"{text} {unquote(text)} {decoded_text}"
        return bool(
            re.search(
                r"\b(?:auto[-\s]?dubbed|dubbed[-\s]?auto|automatically[-\s]?dubbed|"
                r"automatic[-\s]?dubbing|doblado[-\s]?autom[aá]tico|doblaje[-\s]?autom[aá]tico)\b",
                haystack,
            )
        )

    @staticmethod
    def iter_decoded_xtag_texts(value: str) -> list[str]:
        candidates = [value]
        for separator in (";", "&", ",", " "):
            candidates.extend(part for part in value.split(separator) if part)

        decoded: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            cleaned = unquote(candidate).strip().strip('"')
            if not cleaned or "=" in cleaned.rstrip("="):
                continue
            if not re.fullmatch(r"[A-Za-z0-9_-]{12,}={0,2}", cleaned):
                continue
            padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
            try:
                raw = base64.urlsafe_b64decode(padded.encode("ascii"))
            except Exception:
                continue
            text = raw.decode("utf-8", errors="ignore")
            if text and text not in seen:
                seen.add(text)
                decoded.append(text)
        return decoded

    @classmethod
    def extract_published_at_from_info(cls, info: dict[str, Any]) -> str | None:
        for key in ("upload_date", "release_date", "modified_date"):
            normalized = cls.normalize_youtube_date(info.get(key))
            if normalized:
                return normalized
        for key in ("timestamp", "release_timestamp"):
            normalized = cls.normalize_youtube_timestamp(info.get(key))
            if normalized:
                return normalized
        return None

    @staticmethod
    def extract_view_count_from_info(info: dict[str, Any]) -> int | None:
        try:
            raw = info.get("view_count")
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def normalize_youtube_date(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if re.fullmatch(r"\d{8}", text):
            return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
        if re.match(r"\d{4}-\d{2}-\d{2}", text):
            return text[:10]
        return None

    @staticmethod
    def normalize_youtube_timestamp(value: Any) -> str | None:
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()

    @staticmethod
    def extract_view_count(payload: dict[str, Any]) -> int | None:
        raw = payload.get("videoDetails", {}).get("viewCount")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def extract_published_at(payload: dict[str, Any]) -> str | None:
        micro = payload.get("microformat", {}).get("playerMicroformatRenderer", {})
        return (
            micro.get("publishDate")
            or micro.get("uploadDate")
            or None
        )

    @staticmethod
    def extract_published_at_from_html(html: str) -> str | None:
        for key in ("publishDate", "uploadDate", "datePublished"):
            match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', html)
            if match:
                return match.group(1)

        for tag_match in re.finditer(r"<meta\b[^>]*>", html, flags=re.IGNORECASE):
            tag = tag_match.group(0)
            if not re.search(
                r'(?:itemprop|name|property)\s*=\s*["\'](?:publishDate|uploadDate|datePublished)["\']',
                tag,
                flags=re.IGNORECASE,
            ):
                continue
            content = re.search(r'content\s*=\s*["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
            if content:
                return content.group(1)
        return None

    @staticmethod
    def extract_view_count_from_html(html: str) -> int | None:
        for key in ("viewCount", "interactionCount"):
            match = re.search(rf'"{key}"\s*:\s*"?([0-9]+)"?', html)
            if match:
                return int(match.group(1))

        for tag_match in re.finditer(r"<meta\b[^>]*>", html, flags=re.IGNORECASE):
            tag = tag_match.group(0)
            if not re.search(
                r'(?:itemprop|name|property)\s*=\s*["\'](?:interactionCount|viewCount)["\']',
                tag,
                flags=re.IGNORECASE,
            ):
                continue
            content = re.search(r'content\s*=\s*["\']([0-9]+)["\']', tag, flags=re.IGNORECASE)
            if content:
                return int(content.group(1))
        return None

    def discover_related(self, video_id: str) -> list[dict[str, Any]]:
        html = self.fetch_watch_page(video_id)
        return self.extract_related_candidates_from_watch_html(html)

    @classmethod
    def extract_related_candidates_from_watch_html(cls, html: str) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for marker in ("var ytInitialData = ", "ytInitialData = ", "window[\"ytInitialData\"] = "):
            try:
                payloads.append(cls.extract_json_object_after_marker(html, marker))
                break
            except ValueError:
                continue
        for marker in ("var ytInitialPlayerResponse = ", "ytInitialPlayerResponse = "):
            try:
                payloads.append(cls.extract_json_object_after_marker(html, marker))
                break
            except ValueError:
                continue

        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        for payload in payloads:
            for item in cls.extract_related_candidates_from_payload(payload):
                video_id = str(item.get("video_id") or "")
                if video_id and video_id not in seen:
                    seen.add(video_id)
                    candidates.append(item)
        return candidates

    @classmethod
    def extract_related_candidates_from_payload(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(item: dict[str, Any]) -> None:
            video_id = str(item.get("video_id") or "").strip()
            if not video_id or video_id in seen:
                return
            seen.add(video_id)
            item["title"] = item.get("title") or video_id
            candidates.append(item)

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for renderer_key in ("compactVideoRenderer", "videoRenderer", "gridVideoRenderer"):
                    renderer = node.get(renderer_key)
                    if isinstance(renderer, dict):
                        parsed = cls._candidate_from_renderer(renderer)
                        if parsed:
                            add(parsed)
                lockup = node.get("lockupViewModel")
                if isinstance(lockup, dict):
                    parsed = cls._candidate_from_lockup(lockup)
                    if parsed:
                        add(parsed)
                endpoint = node.get("watchEndpoint")
                if isinstance(endpoint, dict) and endpoint.get("videoId"):
                    add({"video_id": endpoint.get("videoId"), "title": endpoint.get("videoId")})
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return candidates

    @staticmethod
    def extract_json_object_after_marker(html: str, marker: str) -> dict[str, Any]:
        start = html.find(marker)
        if start == -1:
            raise ValueError(f"No se encontro {marker.strip()} en la pagina.")

        index = start + len(marker)
        while index < len(html) and html[index].isspace():
            index += 1
        if index >= len(html) or html[index] != "{":
            raise ValueError(f"{marker.strip()} no inicia con un objeto JSON.")

        depth = 0
        in_string = False
        escaped = False
        end = None
        for position in range(index, len(html)):
            char = html[position]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = position + 1
                    break
        if end is None:
            raise ValueError(f"No se pudo aislar el JSON de {marker.strip()}.")
        return json.loads(html[index:end])

    @classmethod
    def _candidate_from_renderer(cls, renderer: dict[str, Any]) -> dict[str, Any] | None:
        video_id = renderer.get("videoId")
        if not video_id:
            return None
        return {
            "video_id": video_id,
            "title": cls._text_value(renderer.get("title")) or video_id,
            "channel": (
                cls._text_value(renderer.get("shortBylineText"))
                or cls._text_value(renderer.get("longBylineText"))
                or cls._text_value(renderer.get("ownerText"))
            ),
            "channel_id": cls._channel_id_from_renderer(renderer),
            "duration_seconds": cls._duration_seconds_from_text(cls._text_value(renderer.get("lengthText"))),
            "thumbnail_url": cls._thumbnail_url(renderer.get("thumbnail")),
            "published_at": None,
            "view_count": cls._view_count_from_text(
                cls._text_value(renderer.get("viewCountText"))
                or cls._text_value(renderer.get("shortViewCountText"))
            ),
        }

    @classmethod
    def _candidate_from_lockup(cls, lockup: dict[str, Any]) -> dict[str, Any] | None:
        video_id = lockup.get("contentId") or lockup.get("videoId")
        if not video_id:
            return None
        metadata = lockup.get("metadata") or {}
        title = cls._find_first_content(metadata, preferred_keys={"title"}) or str(video_id)
        channel = cls._find_first_content(metadata, preferred_keys={"metadata", "subtitle"})
        return {
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "channel_id": None,
            "duration_seconds": None,
            "thumbnail_url": cls._thumbnail_url(lockup),
            "published_at": None,
            "view_count": None,
        }

    @staticmethod
    def _text_value(node: Any) -> str | None:
        if isinstance(node, str):
            return node.strip() or None
        if not isinstance(node, dict):
            return None
        if isinstance(node.get("simpleText"), str):
            return node["simpleText"].strip() or None
        if isinstance(node.get("content"), str):
            return node["content"].strip() or None
        runs = node.get("runs")
        if isinstance(runs, list):
            text = "".join(str(run.get("text") or "") for run in runs if isinstance(run, dict)).strip()
            return text or None
        return None

    @classmethod
    def _find_first_content(cls, node: Any, *, preferred_keys: set[str]) -> str | None:
        if isinstance(node, dict):
            for key in preferred_keys:
                value = node.get(key)
                text = cls._text_value(value)
                if text:
                    return text
            text = cls._text_value(node)
            if text:
                return text
            for value in node.values():
                found = cls._find_first_content(value, preferred_keys=preferred_keys)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = cls._find_first_content(item, preferred_keys=preferred_keys)
                if found:
                    return found
        return None

    @staticmethod
    def _thumbnail_url(node: Any) -> str | None:
        if not isinstance(node, dict):
            return None
        thumbnails = node.get("thumbnails")
        if isinstance(thumbnails, list) and thumbnails:
            last = thumbnails[-1]
            if isinstance(last, dict):
                return last.get("url")
        sources = node.get("sources")
        if isinstance(sources, list) and sources:
            last = sources[-1]
            if isinstance(last, dict):
                return last.get("url")
        for value in node.values():
            if isinstance(value, (dict, list)):
                found = YouTubeService._thumbnail_url(value) if isinstance(value, dict) else None
                if found:
                    return found
                if isinstance(value, list):
                    for item in value:
                        found = YouTubeService._thumbnail_url(item)
                        if found:
                            return found
        return None

    @staticmethod
    def _duration_seconds_from_text(text: str | None) -> int | None:
        if not text:
            return None
        parts = [part for part in text.strip().split(":") if part.isdigit()]
        if not parts:
            return None
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
        return seconds

    @staticmethod
    def _view_count_from_text(text: str | None) -> int | None:
        if not text:
            return None
        compact = text.lower().replace(",", "").strip()
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([kmb])?", compact)
        if not match:
            return None
        multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(match.group(2) or "", 1)
        return int(float(match.group(1)) * multiplier)

    @staticmethod
    def _channel_id_from_renderer(renderer: dict[str, Any]) -> str | None:
        def walk(node: Any) -> str | None:
            if isinstance(node, dict):
                browse = node.get("browseEndpoint")
                if isinstance(browse, dict) and browse.get("browseId"):
                    return str(browse["browseId"])
                for value in node.values():
                    found = walk(value)
                    if found:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = walk(item)
                    if found:
                        return found
            return None

        return walk(renderer)

    @staticmethod
    def extract_player_response(html: str) -> dict[str, Any]:
        return YouTubeService.extract_json_object_after_marker(html, "var ytInitialPlayerResponse = ")

    def resolve_node_path(self) -> Path | None:
        if self.settings.bundled_node_path.exists():
            return self.settings.bundled_node_path
        system_node = shutil.which("node")
        if system_node:
            return Path(system_node)
        return None

    @staticmethod
    def infer_source_type(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return "search"

        lowered = cleaned.lower()
        if cleaned.startswith("@") or cleaned.startswith("/@"):
            return "channel"
        if lowered.startswith(("channel/", "c/", "user/")):
            return "channel"
        if cleaned.startswith("UC") and len(cleaned) >= 20:
            return "channel"

        candidate = cleaned
        if lowered.startswith("www.youtube.com/"):
            candidate = f"https://{cleaned}"
        elif lowered.startswith("youtube.com/"):
            candidate = f"https://www.{cleaned}"

        if candidate.startswith(("http://", "https://")):
            parsed = urlparse(candidate)
            host = parsed.netloc.lower()
            path = parsed.path.strip("/").lower()
            if "youtube.com" in host:
                if path.startswith("@") or path.startswith(("channel/", "c/", "user/")):
                    return "channel"
                if path.endswith(("/videos", "/streams", "/shorts")):
                    return "channel"
                if path and path.split("/", 1)[0] not in {"watch", "results", "playlist", "shorts"}:
                    return "channel"

        return "search"

    @staticmethod
    def normalize_source_value(source_type: str, value: str) -> str:
        cleaned = value.strip()
        if source_type == "channel":
            return YouTubeService.normalize_channel_value(cleaned)
        return cleaned

    @staticmethod
    def normalize_channel_value(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return cleaned

        if cleaned.startswith("@"):
            return f"https://www.youtube.com/{cleaned}/videos"

        if cleaned.startswith("/@"):
            return f"https://www.youtube.com{cleaned}/videos"

        if cleaned.startswith(("channel/", "c/", "user/")):
            return f"https://www.youtube.com/{cleaned}/videos"

        if cleaned.startswith("www.youtube.com/"):
            cleaned = f"https://{cleaned}"
        elif cleaned.startswith("youtube.com/"):
            cleaned = f"https://www.{cleaned}"

        if cleaned.startswith(("http://", "https://")):
            parsed = urlparse(cleaned)
            host = parsed.netloc.lower()
            if "youtube.com" not in host:
                return cleaned

            path = parsed.path.rstrip("/")
            if not path:
                return "https://www.youtube.com"
            if path.endswith(("/videos", "/streams", "/shorts")):
                return cleaned
            return f"https://www.youtube.com{path}/videos"

        if cleaned.startswith("UC") and len(cleaned) >= 20:
            return f"https://www.youtube.com/channel/{cleaned}/videos"

        return f"https://www.youtube.com/@{cleaned.lstrip('@').strip('/')}/videos"

    normalize_channel_url = normalize_channel_value

    @staticmethod
    def _candidate_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
        thumbs = entry.get("thumbnails") or []
        thumbnail_url = thumbs[-1]["url"] if thumbs else None
        duration = entry.get("duration")
        return {
            "video_id": entry.get("id"),
            "title": entry.get("title") or entry.get("id"),
            "channel": entry.get("channel") or entry.get("uploader"),
            "channel_id": entry.get("channel_id"),
            "duration_seconds": int(duration) if duration else None,
            "thumbnail_url": thumbnail_url,
            "published_at": YouTubeService.extract_published_at_from_info(entry),
            "view_count": YouTubeService.extract_view_count_from_info(entry),
        }
