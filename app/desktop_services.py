from __future__ import annotations

import shutil
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any

from .config import Settings, get_settings
from .db import Database
from .discovery_worker import DiscoveryLoop, DiscoveryWorker
from .repository import Repository, SourceInput
from .run_manager import RunManager
from .youtube import StartupDiagnostics, YouTubeService


@dataclass
class DesktopServices:
    settings: Settings
    db: Database
    repo: Repository
    youtube: YouTubeService
    runner: RunManager
    diagnostics: StartupDiagnostics
    discovery_worker: DiscoveryWorker | None = None
    discovery_loop: DiscoveryLoop | None = None


def prepare_runtime_storage(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    legacy_data_dir = settings.legacy_bundle_data_dir
    if not legacy_data_dir.exists():
        return
    if legacy_data_dir.resolve() == settings.data_dir.resolve():
        return
    if settings.db_path.exists():
        return

    shutil.copytree(legacy_data_dir, settings.data_dir, dirs_exist_ok=True)


def build_services() -> DesktopServices:
    settings = get_settings()
    prepare_runtime_storage(settings)
    db = Database(settings.db_path)
    db.initialize()
    repo = Repository(db)
    repo.merge_starter_pack(settings.starter_pack_path, version=settings.starter_pack_version)
    repo.repair_display_metadata_flags()
    repo.recover_scheduler_jobs()
    youtube = YouTubeService(settings)
    diagnostics = youtube.startup_diagnostics()
    runner = RunManager(repo, youtube, settings)
    discovery_worker = DiscoveryWorker(repo, youtube, settings)
    discovery_loop = DiscoveryLoop(
        discovery_worker,
        interval_seconds=int(getattr(settings, "discovery_loop_interval_seconds", 45)),
    )
    discovery_loop.start()
    return DesktopServices(
        settings=settings,
        db=db,
        repo=repo,
        youtube=youtube,
        runner=runner,
        diagnostics=diagnostics,
        discovery_worker=discovery_worker,
        discovery_loop=discovery_loop,
    )


class AppController:
    LAST_MAX_CANDIDATES_KEY = "last_max_candidates_per_run"
    LEGACY_DEFAULT_MAX_CANDIDATES = 50

    def __init__(self, services: DesktopServices) -> None:
        self.services = services

    def dashboard_stats(self) -> dict[str, Any]:
        return self.services.repo.dashboard_stats()

    def list_sources(self) -> list[dict[str, Any]]:
        return self.services.repo.list_sources()

    def create_source(
        self,
        *,
        source_type: str,
        label: str | None,
        value: str,
        max_candidates_per_run: int,
        enabled: bool,
    ) -> int:
        normalized_value = self.services.youtube.normalize_source_value(source_type, value)
        final_label = self._resolve_source_label(source_type, label, value, normalized_value)
        return self.services.repo.create_source(
            SourceInput(
                type=source_type,
                label=final_label,
                value=normalized_value,
                max_candidates_per_run=max_candidates_per_run,
                enabled=enabled,
            )
        )

    def create_quick_source(self, raw_value: str) -> int:
        cleaned = raw_value.strip()
        if not cleaned:
            raise ValueError("Escribe un canal o una búsqueda.")

        source_type = self.services.youtube.infer_source_type(cleaned)
        normalized_value = self.services.youtube.normalize_source_value(source_type, cleaned)
        label = self._suggest_source_label(source_type, cleaned, normalized_value)
        max_candidates = self.get_last_max_candidates()
        return self.services.repo.create_source(
            SourceInput(
                type=source_type,
                label=label,
                value=normalized_value,
                max_candidates_per_run=max_candidates,
                enabled=True,
            )
        )

    def submit_interest(self, raw_value: str) -> dict[str, Any]:
        cleaned = raw_value.strip()
        if not cleaned:
            raise ValueError("Escribe un canal o una busqueda.")
        source_type = self.services.youtube.infer_source_type(cleaned)
        normalized_value = self.services.youtube.normalize_source_value(source_type, cleaned)
        label = self._suggest_source_label(source_type, cleaned, normalized_value)
        seed_kind = "user_channel" if source_type == "channel" else "user_search"
        seed_id = self.services.repo.create_discovery_seed(
            seed_kind=seed_kind,
            source_type=source_type,
            label=label,
            value=normalized_value,
            priority=10,
        )
        if self.services.discovery_loop is not None:
            self.services.discovery_loop.wake()
        return {
            "seed_id": seed_id,
            "source_type": source_type,
            "label": label,
            "value": normalized_value,
        }

    def list_discovery_seeds(self) -> list[dict[str, Any]]:
        return self.services.repo.list_discovery_seeds()

    def run_discovery_once(
        self,
        *,
        max_seed_discoveries: int | None = None,
        max_candidate_inspections: int | None = None,
    ) -> dict[str, int]:
        if self.services.discovery_worker is None:
            return {}
        return self.services.discovery_worker.run_once(
            max_seed_discoveries=max_seed_discoveries,
            max_candidate_inspections=max_candidate_inspections,
        )

    def run_manual_feed_expansion(self, *, candidate_limit: int = 50) -> dict[str, int]:
        if self.services.discovery_worker is None:
            return {}
        return self.services.discovery_worker.run_manual_feed_batch(
            candidate_limit=candidate_limit,
            max_seed_discoveries=10,
        )

    def update_source(
        self,
        source_id: int,
        *,
        source_type: str,
        label: str | None,
        value: str,
        max_candidates_per_run: int,
        enabled: bool,
    ) -> None:
        normalized_value = self.services.youtube.normalize_source_value(source_type, value)
        final_label = self._resolve_source_label(source_type, label, value, normalized_value)
        self.services.repo.update_source(
            source_id,
            SourceInput(
                type=source_type,
                label=final_label,
                value=normalized_value,
                max_candidates_per_run=max_candidates_per_run,
                enabled=enabled,
            ),
        )

    def toggle_source(self, source_id: int) -> None:
        source = self.services.repo.get_source(source_id)
        if not source:
            raise ValueError("Fuente no encontrada")
        self.services.repo.set_source_enabled(source_id, not bool(source["enabled"]))

    def increase_full_source_limits(self, amount: int = 500) -> int:
        return self.services.repo.increase_full_source_limits(amount)

    def delete_source(self, source_id: int, *, delete_videos: bool = False) -> None:
        if not self.services.repo.get_source(source_id):
            raise ValueError("Fuente no encontrada")
        self.services.repo.delete_source(source_id, delete_videos=delete_videos)

    def delete_sources(self, source_ids: list[int], *, delete_videos: bool = False) -> None:
        valid_ids = [int(source_id) for source_id in source_ids if self.services.repo.get_source(int(source_id))]
        if not valid_ids:
            raise ValueError("Selecciona al menos una búsqueda válida.")
        self.services.repo.delete_sources(valid_ids, delete_videos=delete_videos)

    def run_source(self, source_id: int) -> int:
        if not self.services.repo.get_source(source_id):
            raise ValueError("Fuente no encontrada")
        return self.services.runner.start_run(scope=f"source:{source_id}", source_id=source_id)

    def run_all(self) -> int:
        return self.services.runner.start_run(scope="all")

    def start_metadata_backfill(self, *, limit: int | None = None) -> int | None:
        return self.services.runner.start_metadata_backfill(
            limit=limit,
            max_workers=int(getattr(self.services.settings, "metadata_backfill_workers", 1)),
        )

    def count_videos_missing_metadata(self) -> int:
        return self.services.repo.count_videos_missing_metadata(
            classifier_version=self.services.settings.dub_classifier_version
        )

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.services.repo.list_runs(limit=limit)

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        return self.services.repo.get_run(run_id)

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
        return self.services.repo.list_catalog(
            lang=lang or None,
            source_id=source_id,
            channel=channel or None,
            query=query or None,
            only_dubbed=only_dubbed,
            only_favorites=only_favorites,
            dub_kind=dub_kind or None,
            sort_by=sort_by,
            year=year,
            year_after=year_after,
            year_before=year_before,
        )

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
        return self.services.repo.count_catalog(
            lang=lang or None,
            source_id=source_id,
            channel=channel or None,
            query=query or None,
            only_dubbed=only_dubbed,
            only_favorites=only_favorites,
            dub_kind=dub_kind or None,
            year=year,
            year_after=year_after,
            year_before=year_before,
        )

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
        return self.services.repo.list_catalog_page(
            lang=lang or None,
            source_id=source_id,
            channel=channel or None,
            query=query or None,
            only_dubbed=only_dubbed,
            only_favorites=only_favorites,
            dub_kind=dub_kind or None,
            sort_by=sort_by,
            year=year,
            year_after=year_after,
            year_before=year_before,
            page_size=page_size,
            cursor=cursor,
        )

    def set_video_favorite(self, video_id: str, is_favorite: bool) -> None:
        self.services.repo.set_video_favorite(video_id, is_favorite)

    def list_catalog_filters(self) -> dict[str, list[Any]]:
        return self.services.repo.list_catalog_filters()

    def active_run_id(self) -> int | None:
        return self.services.runner.active_run_id()

    def active_run_snapshot(self) -> dict[str, Any] | None:
        active_run_id = self.services.runner.active_run_id()
        if active_run_id is None:
            return None
        return self.services.repo.get_run(active_run_id)

    def get_last_max_candidates(self) -> int:
        raw = self.services.repo.get_preference(self.LAST_MAX_CANDIDATES_KEY)
        if raw is None:
            return int(self.services.settings.default_search_candidates)
        try:
            parsed = max(1, min(10000, int(raw)))
        except (TypeError, ValueError):
            return int(self.services.settings.default_search_candidates)
        if parsed == self.LEGACY_DEFAULT_MAX_CANDIDATES:
            return int(self.services.settings.default_search_candidates)
        return parsed

    def set_last_max_candidates(self, value: int) -> None:
        safe_value = max(1, min(10000, int(value)))
        self.services.repo.set_preference(self.LAST_MAX_CANDIDATES_KEY, str(safe_value))

    @classmethod
    def _resolve_source_label(
        cls,
        source_type: str,
        label: str | None,
        raw_value: str,
        normalized_value: str,
    ) -> str:
        if label and label.strip():
            return label.strip()
        return cls._suggest_source_label(source_type, raw_value, normalized_value)

    @staticmethod
    def _suggest_source_label(source_type: str, raw_value: str, normalized_value: str) -> str:
        if source_type == "channel":
            parsed = urlparse(normalized_value)
            parts = [part for part in parsed.path.split("/") if part]
            if parts:
                if parts[0].startswith("@"):
                    return parts[0].lstrip("@")
                if parts[0] in {"channel", "c", "user"} and len(parts) > 1:
                    return parts[1]
                return parts[0]
            return raw_value.strip().lstrip("@") or "Canal"

        words = raw_value.strip().split()
        if not words:
            return "Búsqueda"
        label = " ".join(words[:4]).strip()
        return label[:48].rstrip() or "Búsqueda"
