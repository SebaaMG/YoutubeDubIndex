from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from .config import Settings
from .repository import CandidateVideo, Repository, to_iso, utc_now
from .youtube import InspectionResult, YouTubeService


class RunManager:
    def __init__(self, repo: Repository, youtube: YouTubeService, settings: Settings) -> None:
        self.repo = repo
        self.youtube = youtube
        self.settings = settings
        self._lock = threading.Lock()
        self._active_run_id: int | None = None
        self._active_thread: threading.Thread | None = None
        self._event_callback: Callable[[dict[str, Any]], None] | None = None

    def is_active(self) -> bool:
        with self._lock:
            return self._active_run_id is not None

    def active_run_id(self) -> int | None:
        with self._lock:
            return self._active_run_id

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

    def start_run(self, *, scope: str, source_id: int | None = None) -> int:
        with self._lock:
            if self._active_run_id is not None:
                raise RuntimeError("Ya hay un scraping en ejecución")

            run_id = self.repo.create_run(scope)
            self.repo.enqueue_job(
                job_type="discover_source",
                payload={"scope": scope, "source_id": source_id},
                idempotency_key=f"run:{run_id}:discover:{source_id or 'all'}",
                priority=50,
                run_id=run_id,
            )
            thread = threading.Thread(
                target=self._run_wrapper,
                args=(run_id, source_id),
                daemon=True,
                name=f"dub-run-{run_id}",
            )
            self._active_run_id = run_id
            self._active_thread = thread
            thread.start()
            self._emit_event({"event": "run_started", "run_id": run_id})
            return run_id

    @property
    def dub_classifier_version(self) -> int:
        return int(getattr(self.settings, "dub_classifier_version", 7))

    def _run_wrapper(self, run_id: int, source_id: int | None) -> None:
        try:
            self.repo.mark_run_running(run_id)
            warning = self._execute(run_id, source_id)
            self.repo.finish_run(run_id, status="completed", error=warning)
            self._emit_event({"event": "run_finished", "run_id": run_id, "status": "completed"})
        except Exception as exc:
            self.repo.finish_run(run_id, status="failed", error=str(exc)[:500])
            self._emit_event({"event": "run_finished", "run_id": run_id, "status": "failed", "error": str(exc)[:500]})
        finally:
            with self._lock:
                self._active_run_id = None
                self._active_thread = None

    def _execute(self, run_id: int, source_id: int | None) -> str | None:
        sources = [self.repo.get_source(source_id)] if source_id else self.repo.list_enabled_sources()
        sources = [source for source in sources if source]
        if not sources:
            raise RuntimeError("No hay fuentes habilitadas para ejecutar.")

        videos_to_inspect: set[str] = set()
        source_errors: list[str] = []
        successful_sources = 0

        for source in sources:
            discovered_at = to_iso(utc_now())
            try:
                discovered = self.youtube.discover_source(source)
            except Exception as exc:
                source_errors.append(f"source:{source['id']} {source['label']}: {str(exc)[:180]}")
                continue

            successful_sources += 1
            self.repo.increment_run_metrics(run_id, candidates_found=len(discovered))

            candidates = [
                CandidateVideo(
                    video_id=item["video_id"],
                    title=item["title"],
                    channel=item.get("channel"),
                    channel_id=item.get("channel_id"),
                    duration_seconds=item.get("duration_seconds"),
                    thumbnail_url=item.get("thumbnail_url"),
                    source_id=source["id"],
                    discovered_at=discovered_at,
                    published_at=item.get("published_at"),
                    view_count=item.get("view_count"),
                )
                for item in discovered
            ]
            self.repo.upsert_candidates_batch(candidates)
            videos_to_inspect.update(
                self.repo.select_inspection_needed(
                    [candidate.video_id for candidate in candidates],
                    self.settings.inspect_stale_days,
                    self.dub_classifier_version,
                )
            )

        backfill_limit = int(getattr(self.settings, "metadata_backfill_limit", 50))
        for missing_video_id in self.repo.list_video_ids_missing_metadata(
            source_id=source_id,
            limit=backfill_limit,
            classifier_version=self.dub_classifier_version,
        ):
            videos_to_inspect.add(missing_video_id)

        if not videos_to_inspect:
            return

        self._inspect_video_ids(run_id, videos_to_inspect)

        if successful_sources == 0 and source_errors:
            raise RuntimeError(" / ".join(source_errors)[:500])

        if source_errors:
            return " / ".join(source_errors)[:500]
        return None

    def start_metadata_backfill(self, *, limit: int | None = None, max_workers: int | None = None) -> int | None:
        backfill_limit = int(limit or getattr(self.settings, "metadata_backfill_limit", 50))
        video_ids = self.repo.list_video_ids_missing_metadata(
            limit=backfill_limit,
            classifier_version=self.dub_classifier_version,
        )
        if not video_ids:
            return None

        with self._lock:
            if self._active_run_id is not None:
                return None

            run_id = self.repo.create_run("metadata")
            thread = threading.Thread(
                target=self._metadata_backfill_wrapper,
                args=(run_id, set(video_ids), max_workers),
                daemon=True,
                name=f"dub-metadata-{run_id}",
            )
            self._active_run_id = run_id
            self._active_thread = thread
            thread.start()
            self._emit_event({"event": "run_started", "run_id": run_id})
            return run_id

    def _metadata_backfill_wrapper(self, run_id: int, video_ids: set[str], max_workers: int | None) -> None:
        try:
            self.repo.mark_run_running(run_id)
            self.repo.increment_run_metrics(run_id, candidates_found=len(video_ids))
            self._inspect_video_ids(run_id, video_ids, max_workers=max_workers)
            self.repo.finish_run(run_id, status="completed")
            self._emit_event({"event": "run_finished", "run_id": run_id, "status": "completed"})
        except Exception as exc:
            self.repo.finish_run(run_id, status="failed", error=str(exc)[:500])
            self._emit_event({"event": "run_finished", "run_id": run_id, "status": "failed", "error": str(exc)[:500]})
        finally:
            with self._lock:
                self._active_run_id = None
                self._active_thread = None

    def _inspect_video_ids(self, run_id: int, video_ids: set[str], max_workers: int | None = None) -> None:
        worker_count = int(max_workers or self.settings.inspect_workers)
        batch_size = max(10, int(getattr(self.settings, "inspect_batch_size", 200)))
        sorted_ids = sorted(video_ids)
        with ThreadPoolExecutor(max_workers=max(1, worker_count)) as executor:
            for start in range(0, len(sorted_ids), batch_size):
                batch_ids = sorted_ids[start : start + batch_size]
                future_map = {
                    executor.submit(self._inspect_with_retry, video_id): video_id
                    for video_id in batch_ids
                }
                result_payloads: list[dict[str, Any]] = []
                failures: list[tuple[str, str]] = []
                dubbed_found = 0
                for future in as_completed(future_map):
                    video_id = future_map[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        failures.append((video_id, str(exc)))
                        continue

                    result_payloads.append(
                        {
                            "video_id": video_id,
                            "audio_languages": result.audio_languages,
                            "has_dubbing": result.has_dubbing,
                            "published_at": result.published_at,
                            "view_count": result.view_count,
                            "dub_kind": result.dub_kind,
                            "title": result.title,
                            "channel": result.channel,
                            "channel_id": result.channel_id,
                            "duration_seconds": result.duration_seconds,
                            "thumbnail_url": result.thumbnail_url,
                            "dub_confidence": getattr(result, "dub_confidence", None),
                            "dub_evidence": getattr(result, "dub_evidence", None),
                            "classifier_version": self.dub_classifier_version,
                        }
                    )
                    if result.has_dubbing:
                        dubbed_found += 1

                self.repo.store_inspection_results_batch(result_payloads)
                self.repo.store_inspection_failures_batch(failures)
                self.repo.increment_run_metrics(
                    run_id,
                    videos_checked=len(result_payloads) + len(failures),
                    dubbed_found=dubbed_found,
                )
                self._emit_event(
                    {
                        "event": "run_progress",
                        "run_id": run_id,
                        "videos_checked": len(result_payloads) + len(failures),
                        "dubbed_found": dubbed_found,
                    }
                )

    def _inspect_with_retry(self, video_id: str) -> InspectionResult:
        attempts = self.settings.inspect_retry_attempts + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return self.youtube.inspect_video(video_id)
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                time.sleep(attempt)
        assert last_error is not None
        raise last_error
