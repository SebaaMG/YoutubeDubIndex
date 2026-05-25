from __future__ import annotations

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from .config import Settings
from .repository import Repository
from .youtube import YouTubeService


class DiscoveryWorker:
    def __init__(self, repo: Repository, youtube: YouTubeService, settings: Settings) -> None:
        self.repo = repo
        self.youtube = youtube
        self.settings = settings
        self._run_lock = threading.Lock()
        self._event_callback: Callable[[dict[str, Any]], None] | None = None

    def set_event_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        self._event_callback = callback

    def _emit_event(self, payload: dict[str, Any]) -> None:
        callback = self._event_callback
        if callback is None:
            return
        try:
            callback(payload)
        except Exception:
            pass

    def run_once(
        self,
        *,
        max_seed_discoveries: int | None = None,
        max_candidate_inspections: int | None = None,
        randomize_seeds: bool = False,
        seed_rescan_delay_minutes: int = 240,
    ) -> dict[str, int]:
        with self._run_lock:
            return self._run_once_unlocked(
                max_seed_discoveries=max_seed_discoveries,
                max_candidate_inspections=max_candidate_inspections,
                randomize_seeds=randomize_seeds,
                seed_rescan_delay_minutes=seed_rescan_delay_minutes,
            )

    def _run_once_unlocked(
        self,
        *,
        max_seed_discoveries: int | None = None,
        max_candidate_inspections: int | None = None,
        randomize_seeds: bool = False,
        seed_rescan_delay_minutes: int = 240,
    ) -> dict[str, int]:
        configured_seed_batch = max(1, min(50, int(getattr(self.settings, "discovery_seed_batch", 25))))
        inspect_limit = int(
            getattr(self.settings, "discovery_inspect_batch", 250)
            if max_candidate_inspections is None
            else max_candidate_inspections
        )
        seed_budget = (
            max(configured_seed_batch, max(0, inspect_limit))
            if max_seed_discoveries is None
            else max(0, int(max_seed_discoveries))
        )
        summary = {
            "target": inspect_limit,
            "seeds": 0,
            "related_candidates": 0,
            "inspected": 0,
            "verified": 0,
            "rejected": 0,
            "failed": 0,
            "candidate_unique_channels": 0,
            "candidate_top_channel_count": 0,
            "candidate_top_channel_percent": 0.0,
            "seed_unique_channels": 0,
            "seed_top_channel_count": 0,
        }

        claimed_seeds: list[dict[str, Any]] = []
        claimed_candidates: list[dict[str, Any]] = []
        remaining = max(0, inspect_limit)
        chunk_size = max(1, min(50, int(getattr(self.settings, "discovery_inspection_chunk_size", 50))))
        while remaining > 0:
            chunk = self.repo.claim_frontier_candidates(limit=min(chunk_size, remaining))
            if chunk:
                claimed_candidates.extend(chunk)
                self._process_candidate_chunk(chunk, summary)
                remaining -= len(chunk)
                continue

            if seed_budget <= 0:
                break
            seed_batch = self.repo.claim_discovery_seeds_mixed(
                limit=min(configured_seed_batch, seed_budget),
                randomize=randomize_seeds,
            )
            if not seed_batch:
                break
            seed_budget -= len(seed_batch)
            claimed_seeds.extend(seed_batch)
            for seed in seed_batch:
                summary["seeds"] += 1
                try:
                    candidates = self._discover_seed(seed)
                except Exception:
                    self.repo.mark_discovery_seed_scanned(int(seed["id"]), delay_minutes=60)
                    summary["failed"] += 1
                    continue
                if candidates:
                    self.repo.enqueue_candidates_batch(
                        candidates,
                        source_seed_id=int(seed["id"]),
                        discovered_from_video_id=str(seed["value"]) if seed["source_type"] == "video" else None,
                        priority=max(1, int(seed["priority"] or 100) + 10),
                        score=1.0,
                    )
                summary["related_candidates"] += len(candidates)
                self.repo.mark_discovery_seed_scanned(int(seed["id"]), delay_minutes=seed_rescan_delay_minutes)

        self._apply_seed_metrics(summary, claimed_seeds)
        self._apply_candidate_metrics(summary, claimed_candidates)
        if summary["inspected"] or summary["related_candidates"]:
            self._emit_event({"event": "summary_dirty", "summary": dict(summary)})
        if summary["inspected"]:
            self._emit_discovery_progress(summary, active=False)
        return summary

    def _emit_discovery_progress(self, summary: dict[str, int | float], *, active: bool = True) -> None:
        target = int(summary.get("target") or 0)
        inspected = int(summary.get("inspected") or 0)
        self._emit_event(
            {
                "event": "discovery_progress" if active else "discovery_finished",
                "scope": "exploración",
                "active": active,
                "target": max(target, inspected, 1),
                "inspected": inspected,
                "verified": int(summary.get("verified") or 0),
                "rejected": int(summary.get("rejected") or 0),
                "failed": int(summary.get("failed") or 0),
            }
        )

    def _process_candidate_chunk(
        self,
        claimed_candidates: list[dict[str, Any]],
        summary: dict[str, int | float],
    ) -> None:
        result_payloads: list[dict[str, Any]] = []
        verified_video_ids: list[str] = []
        rejected_video_ids: list[str] = []
        failed_candidates: list[tuple[str, str, int]] = []
        related_seed_payloads: list[dict[str, Any]] = []
        verified_seed_rows: list[dict[str, Any]] = []
        inspected_results = self._inspect_candidates(claimed_candidates)
        for candidate, result, error in inspected_results:
            video_id = str(candidate["video_id"])
            summary["inspected"] += 1
            if error is not None:
                attempts = int(candidate.get("attempts") or 0)
                failed_candidates.append((video_id, str(error), min(24 * 60, 30 * (attempts + 1))))
                summary["failed"] += 1
                continue
            if result is None:
                failed_candidates.append((video_id, "La inspeccion no devolvio resultado.", 30))
                summary["failed"] += 1
                continue

            if not result.has_dubbing:
                rejected_video_ids.append(video_id)
                summary["rejected"] += 1
                continue

            result_payloads.append(
                {
                    "video_id": video_id,
                    "audio_languages": result.audio_languages,
                    "has_dubbing": True,
                    "published_at": result.published_at or candidate.get("published_at"),
                    "view_count": result.view_count if result.view_count is not None else candidate.get("view_count"),
                    "dub_kind": result.dub_kind,
                    "title": result.title or candidate.get("title"),
                    "channel": result.channel or candidate.get("channel"),
                    "channel_id": result.channel_id or candidate.get("channel_id"),
                    "duration_seconds": (
                    result.duration_seconds
                    if result.duration_seconds is not None
                    else candidate.get("duration_seconds")
                    ),
                    "thumbnail_url": result.thumbnail_url or candidate.get("thumbnail_url"),
                    "dub_confidence": getattr(result, "dub_confidence", None),
                    "dub_evidence": getattr(result, "dub_evidence", None),
                    "classifier_version": getattr(self.settings, "dub_classifier_version", 6),
                }
            )
            verified_video_ids.append(video_id)
            verified_seed_rows.append(
                {
                    "video_id": video_id,
                    "title": result.title or str(candidate.get("title") or video_id),
                    "channel_id": result.channel_id or candidate.get("channel_id"),
                    "channel": result.channel or candidate.get("channel"),
                    "value": video_id,
                }
            )
            summary["verified"] += 1

        if verified_seed_rows:
            seed_count_cache = self.repo.count_video_discovery_seeds_by_channel_keys(verified_seed_rows)
            for seed_row in verified_seed_rows:
                channel_key = self._row_channel_key(seed_row)
                same_channel_seed_count = seed_count_cache.get(channel_key, 0)
                seed_count_cache[channel_key] = same_channel_seed_count + 1
                seed_priority = 80 + min(50, same_channel_seed_count * 2)
                related_seed_payloads.append(
                    {
                        "seed_kind": "related_video",
                        "source_type": "video",
                        "label": str(seed_row.get("title") or seed_row["video_id"]),
                        "value": str(seed_row["video_id"]),
                        "priority": min(130, seed_priority),
                    }
                )

        if result_payloads:
            self.repo.store_inspection_results_batch(result_payloads)
        if verified_video_ids:
            self.repo.mark_candidates_verified(verified_video_ids)
        if related_seed_payloads:
            self.repo.create_discovery_seeds_batch(related_seed_payloads)
        if rejected_video_ids:
            self.repo.mark_candidates_rejected(rejected_video_ids, "no dubbing")
        if failed_candidates:
            self.repo.mark_candidates_failed(failed_candidates)
        if verified_video_ids:
            self._emit_event(
                {
                    "event": "catalog_changed",
                    "verified": len(verified_video_ids),
                    "inspected": len(claimed_candidates),
                    "summary": dict(summary),
                }
            )
        elif claimed_candidates:
            self._emit_event(
                {
                    "event": "summary_dirty",
                    "inspected": len(claimed_candidates),
                    "summary": dict(summary),
                }
            )
        if claimed_candidates:
            self._emit_discovery_progress(summary, active=True)

    def _inspect_candidates(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], Any | None, Exception | None]]:
        if not candidates:
            return []
        worker_count = max(
            1,
            min(
                len(candidates),
                int(getattr(self.settings, "discovery_inspect_workers", getattr(self.settings, "inspect_workers", 4))),
            ),
        )
        if worker_count <= 1:
            results: list[tuple[dict[str, Any], Any | None, Exception | None]] = []
            for candidate in candidates:
                try:
                    results.append((candidate, self.youtube.inspect_video(str(candidate["video_id"])), None))
                except Exception as exc:
                    results.append((candidate, None, exc))
            return results

        results = []
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="discovery-inspect") as executor:
            future_map = {
                executor.submit(self.youtube.inspect_video, str(candidate["video_id"])): candidate
                for candidate in candidates
            }
            for future in as_completed(future_map):
                candidate = future_map[future]
                try:
                    results.append((candidate, future.result(), None))
                except Exception as exc:
                    results.append((candidate, None, exc))
        return results

    @staticmethod
    def _row_channel_key(row: dict[str, Any]) -> str:
        if row.get("channel_key"):
            return str(row["channel_key"])
        if row.get("seed_channel_key"):
            return str(row["seed_channel_key"])
        channel_id = str(row.get("channel_id") or "").strip()
        if channel_id:
            return f"id:{channel_id}"
        channel = str(row.get("channel") or "").strip()
        if channel:
            return f"name:{channel.lower()}"
        video_id = str(row.get("video_id") or row.get("value") or row.get("id") or "").strip()
        return f"video:{video_id}" if video_id else "unknown"

    @classmethod
    def _channel_counts(cls, rows: list[dict[str, Any]]) -> Counter[str]:
        return Counter(cls._row_channel_key(row) for row in rows)

    @classmethod
    def _apply_seed_metrics(cls, summary: dict[str, int | float], rows: list[dict[str, Any]]) -> None:
        counts = cls._channel_counts(rows)
        summary["seed_unique_channels"] = len(counts)
        summary["seed_top_channel_count"] = max(counts.values(), default=0)

    @classmethod
    def _apply_candidate_metrics(cls, summary: dict[str, int | float], rows: list[dict[str, Any]]) -> None:
        counts = cls._channel_counts(rows)
        top_count = max(counts.values(), default=0)
        summary["candidate_unique_channels"] = len(counts)
        summary["candidate_top_channel_count"] = top_count
        summary["candidate_top_channel_percent"] = round((top_count / len(rows)) * 100, 2) if rows else 0.0

    def run_manual_feed_batch(
        self,
        *,
        candidate_limit: int = 50,
        max_seed_discoveries: int | None = None,
    ) -> dict[str, int]:
        safe_limit = max(1, min(250, int(candidate_limit)))
        seed_limit = int(max_seed_discoveries) if max_seed_discoveries is not None else None
        return self.run_once(
            max_seed_discoveries=seed_limit,
            max_candidate_inspections=safe_limit,
            randomize_seeds=True,
            seed_rescan_delay_minutes=15,
        )

    def enqueue_immediate_seed_candidates(
        self,
        seed_id: int,
        *,
        candidate_limit: int = 150,
    ) -> dict[str, int]:
        seed = self.repo.get_discovery_seed(int(seed_id))
        if not seed:
            raise ValueError("Interes no encontrado.")
        safe_limit = max(1, min(250, int(candidate_limit)))
        summary = {
            "seeds": 1,
            "related_candidates": 0,
            "inspected": 0,
            "verified": 0,
            "rejected": 0,
            "failed": 0,
            "candidate_unique_channels": 0,
            "candidate_top_channel_count": 0,
            "candidate_top_channel_percent": 0.0,
            "seed_unique_channels": 1,
            "seed_top_channel_count": 1,
        }
        try:
            candidates = self._discover_seed(seed, candidate_limit=safe_limit)
        except Exception:
            self.repo.mark_discovery_seed_scanned(int(seed["id"]), delay_minutes=60)
            summary["failed"] = 1
            raise

        if candidates:
            self.repo.enqueue_candidates_batch(
                candidates,
                source_seed_id=int(seed["id"]),
                discovered_from_video_id=str(seed["value"]) if seed["source_type"] == "video" else None,
                priority=max(1, int(seed["priority"] or 100) + 10),
                score=1.0,
            )
        summary["related_candidates"] = len(candidates)
        self.repo.mark_discovery_seed_scanned(int(seed["id"]), delay_minutes=15)
        return summary

    def _discover_seed(
        self,
        seed: dict[str, Any],
        *,
        candidate_limit: int | None = None,
    ) -> list[dict[str, Any]]:
        source_type = str(seed["source_type"])
        if source_type == "video":
            return self.youtube.discover_related(str(seed["value"]))
        if source_type in {"search", "channel"}:
            return self.youtube.discover_source(
                {
                    "type": source_type,
                    "value": seed["value"],
                    "max_candidates_per_run": int(
                        candidate_limit
                        if candidate_limit is not None
                        else getattr(self.settings, "discovery_seed_candidate_limit", 50)
                    ),
                }
            )
        return []


class DiscoveryLoop:
    def __init__(
        self,
        worker: DiscoveryWorker,
        *,
        interval_seconds: int = 300,
        enabled: bool = True,
    ) -> None:
        self.worker = worker
        self.interval_seconds = max(5, int(interval_seconds))
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._enabled = threading.Event()
        if enabled:
            self._enabled.set()
        self._pause_lock = threading.Lock()
        self._paused_until = 0.0
        self._thread: threading.Thread | None = None
        self._event_callback: Callable[[dict[str, Any]], None] | None = None

    def set_event_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        self._event_callback = callback
        if hasattr(self.worker, "set_event_callback"):
            self.worker.set_event_callback(callback)

    def _emit_event(self, payload: dict[str, Any]) -> None:
        callback = self._event_callback
        if callback is None:
            return
        try:
            callback(payload)
        except Exception:
            pass

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

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._enabled.set()
        else:
            self._enabled.clear()
        self._wake.set()

    def is_enabled(self) -> bool:
        return self._enabled.is_set()

    def pause_for(self, seconds: float) -> None:
        until = time.monotonic() + max(0.05, float(seconds))
        with self._pause_lock:
            self._paused_until = max(self._paused_until, until)

    def resume(self) -> None:
        with self._pause_lock:
            self._paused_until = 0.0
        self._wake.set()

    def _pause_remaining(self) -> float:
        with self._pause_lock:
            return max(0.0, self._paused_until - time.monotonic())

    def _run(self) -> None:
        self._wake.wait(3)
        while not self._stop.is_set():
            self._wake.clear()
            if not self._enabled.is_set():
                self._wake.wait(self.interval_seconds)
                continue
            remaining = self._pause_remaining()
            if remaining > 0:
                self._wake.wait(min(self.interval_seconds, remaining))
                continue
            try:
                summary = self.worker.run_once()
                if summary.get("verified"):
                    self._emit_event({"event": "catalog_changed", "summary": summary})
                elif summary.get("inspected") or summary.get("related_candidates"):
                    self._emit_event({"event": "summary_dirty", "summary": summary})
            except Exception:
                pass
            self._wake.wait(self.interval_seconds)
