from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.db import Database
from app.discovery_worker import DiscoveryWorker
from app.repository import Repository, to_iso
from app.youtube import YouTubeService


def frontier_counts(repo: Repository) -> dict[str, int]:
    with repo.db.connect(profile="ui_read") as conn:
        rows = conn.execute(
            """
            SELECT state, COUNT(*) AS count
            FROM candidate_frontier
            GROUP BY state
            """
        ).fetchall()
        ready_failed = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM candidate_frontier
            WHERE state = 'failed' AND not_before <= ?
            """,
            (to_iso(),),
        ).fetchone()["count"]
    counts = {str(row["state"]): int(row["count"]) for row in rows}
    counts["failed_ready"] = int(ready_failed or 0)
    counts["ready"] = int(counts.get("queued", 0)) + int(counts.get("failed_ready", 0))
    return counts


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Drain queued discovery candidates without discovering new seeds.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--batch", type=int, default=250)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunk", type=int, default=50)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--max-rounds", type=int, default=0)
    args = parser.parse_args()

    base_settings = get_settings()
    settings = replace(
        base_settings,
        discovery_inspect_batch=max(1, int(args.batch)),
        discovery_inspect_workers=max(1, int(args.workers)),
        discovery_inspection_chunk_size=max(1, int(args.chunk)),
    )
    db = Database(args.db)
    db.default_profile = "worker_write"
    db.initialize()
    repo = Repository(db)
    recovered = repo.recover_frontier_candidates(stale_after_minutes=1)
    youtube = YouTubeService(settings)
    worker = DiscoveryWorker(repo, youtube, settings)
    worker.set_event_callback(lambda payload: emit({"event": "worker_event", "payload": payload}))

    started = time.monotonic()
    counts = frontier_counts(repo)
    emit({"event": "start", "db": str(args.db), "recovered": recovered, "counts": counts})
    rounds = 0
    while counts.get("ready", 0) > 0:
        if args.max_rounds and rounds >= args.max_rounds:
            break
        rounds += 1
        round_started = time.monotonic()
        summary = worker.run_once(max_seed_discoveries=0, max_candidate_inspections=args.batch)
        counts = frontier_counts(repo)
        emit(
            {
                "event": "round",
                "round": rounds,
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "round_seconds": round(time.monotonic() - round_started, 1),
                "summary": summary,
                "counts": counts,
            }
        )
        if int(summary.get("inspected") or 0) <= 0:
            break
        if args.sleep > 0:
            time.sleep(float(args.sleep))
    emit({"event": "done", "rounds": rounds, "elapsed_seconds": round(time.monotonic() - started, 1), "counts": counts})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
