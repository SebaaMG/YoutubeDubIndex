from __future__ import annotations

import threading
import time
from typing import Any

from .config import Settings
from .repository import Repository
from .youtube import YouTubeService


class DiscoveryWorker:
    def __init__(self, repo: Repository, youtube: YouTubeService, settings: Settings) -> None:
        self.repo = repo
        self.youtube = youtube
        self.settings = settings

    def run_once(
        self,
        *,
        max_seed_discoveries: int | None = None,
        max_candidate_inspections: int | None = None,
        randomize_seeds: bool = False,
        seed_rescan_delay_minutes: int = 240,
    ) -> dict[str, int]:
        seed_limit = int(max_seed_discoveries or getattr(self.settings, "discovery_seed_batch", 2))
        inspect_limit = int(max_candidate_inspections or getattr(self.settings, "discovery_inspect_batch", 12))
        summary = {
            "seeds": 0,
            "related_candidates": 0,
            "inspected": 0,
            "verified": 0,
            "rejected": 0,
            "failed": 0,
        }

        for seed in self.repo.claim_discovery_seeds(limit=seed_limit, randomize=randomize_seeds):
            summary["seeds"] += 1
            try:
                candidates = self._discover_seed(seed)
            except Exception as exc:
                self.repo.mark_discovery_seed_scanned(int(seed["id"]), delay_minutes=60)
                summary["failed"] += 1
                continue
            for candidate in candidates:
                self.repo.enqueue_candidate(
                    candidate,
                    source_seed_id=int(seed["id"]),
                    discovered_from_video_id=str(seed["value"]) if seed["source_type"] == "video" else None,
                    priority=max(1, int(seed["priority"] or 100) + 10),
                    score=1.0,
                )
            summary["related_candidates"] += len(candidates)
            self.repo.mark_discovery_seed_scanned(int(seed["id"]), delay_minutes=seed_rescan_delay_minutes)

        for candidate in self.repo.claim_frontier_candidates(limit=inspect_limit):
            video_id = str(candidate["video_id"])
            summary["inspected"] += 1
            try:
                result = self.youtube.inspect_video(video_id)
            except Exception as exc:
                attempts = int(candidate.get("attempts") or 0)
                self.repo.mark_candidate_failed(video_id, str(exc), delay_minutes=min(24 * 60, 30 * (attempts + 1)))
                summary["failed"] += 1
                continue

            if not result.has_dubbing:
                self.repo.mark_candidate_rejected(video_id, "no dubbing")
                summary["rejected"] += 1
                continue

            self.repo.store_inspection_result(
                video_id,
                audio_languages=result.audio_languages,
                has_dubbing=True,
                published_at=result.published_at or candidate.get("published_at"),
                view_count=result.view_count if result.view_count is not None else candidate.get("view_count"),
                dub_kind=result.dub_kind,
                title=result.title or candidate.get("title"),
                channel=result.channel or candidate.get("channel"),
                channel_id=result.channel_id or candidate.get("channel_id"),
                duration_seconds=(
                    result.duration_seconds
                    if result.duration_seconds is not None
                    else candidate.get("duration_seconds")
                ),
                thumbnail_url=result.thumbnail_url or candidate.get("thumbnail_url"),
                dub_confidence=getattr(result, "dub_confidence", None),
                dub_evidence=getattr(result, "dub_evidence", None),
                classifier_version=getattr(self.settings, "dub_classifier_version", 6),
            )
            self.repo.mark_candidate_verified(video_id)
            self.repo.create_discovery_seed(
                seed_kind="related_video",
                source_type="video",
                label=result.title or str(candidate.get("title") or video_id),
                value=video_id,
                priority=80,
            )
            summary["verified"] += 1

        return summary

    def run_manual_feed_batch(
        self,
        *,
        candidate_limit: int = 50,
        max_seed_discoveries: int | None = None,
    ) -> dict[str, int]:
        safe_limit = max(1, min(200, int(candidate_limit)))
        seed_limit = int(max_seed_discoveries or max(1, min(10, (safe_limit + 9) // 10)))
        return self.run_once(
            max_seed_discoveries=seed_limit,
            max_candidate_inspections=safe_limit,
            randomize_seeds=True,
            seed_rescan_delay_minutes=15,
        )

    def _discover_seed(self, seed: dict[str, Any]) -> list[dict[str, Any]]:
        source_type = str(seed["source_type"])
        if source_type == "video":
            return self.youtube.discover_related(str(seed["value"]))
        if source_type in {"search", "channel"}:
            return self.youtube.discover_source(
                {
                    "type": source_type,
                    "value": seed["value"],
                    "max_candidates_per_run": int(getattr(self.settings, "discovery_seed_candidate_limit", 50)),
                }
            )
        return []


class DiscoveryLoop:
    def __init__(self, worker: DiscoveryWorker, *, interval_seconds: int = 45) -> None:
        self.worker = worker
        self.interval_seconds = max(5, int(interval_seconds))
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="dub-discovery-loop")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        self._wake.wait(3)
        while not self._stop.is_set():
            self._wake.clear()
            try:
                self.worker.run_once()
            except Exception:
                pass
            self._wake.wait(self.interval_seconds)
