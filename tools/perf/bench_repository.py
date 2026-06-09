from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.db import Database  # noqa: E402
from app.repository import Repository, SPANISH_LANGUAGE_FILTER  # noqa: E402


def timed(label: str, fn, iterations: int = 5) -> None:
    samples = []
    last = None
    for _ in range(iterations):
        start = time.perf_counter()
        last = fn()
        samples.append((time.perf_counter() - start) * 1000)
    p50 = statistics.median(samples)
    p95 = sorted(samples)[min(len(samples) - 1, int(len(samples) * 0.95))]
    size = ""
    if isinstance(last, list):
        size = f" rows={len(last)}"
    elif isinstance(last, dict) and "items" in last:
        size = f" rows={len(last['items'])} next={bool(last.get('next_cursor'))}"
    elif isinstance(last, int):
        size = f" count={last}"
    print(f"{label}: p50={p50:.1f}ms p95={p95:.1f}ms{size}")


def explain(db_path: Path, sql: str, params: list[object]) -> None:
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    for row in rows:
        print("plan:", row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=7)
    args = parser.parse_args()

    repo = Repository(Database(args.db))
    filters = dict(
        lang=SPANISH_LANGUAGE_FILTER,
        source_id=None,
        channel=None,
        query=None,
        only_dubbed=True,
        only_favorites=False,
        dub_kind="manual",
        year=None,
        year_after=None,
        year_before=None,
    )
    timed("count spanish manual", lambda: repo.count_catalog(**filters), args.iterations)
    timed(
        "page recent",
        lambda: repo.list_catalog_page(**filters, sort_by="recent", page_size=160, cursor=None),
        args.iterations,
    )
    timed(
        "page views",
        lambda: repo.list_catalog_page(**filters, sort_by="views", page_size=160, cursor=None),
        args.iterations,
    )
    timed(
        "page random",
        lambda: repo.list_catalog_page(**filters, sort_by="random", page_size=160, cursor=None),
        args.iterations,
    )
    timed(
        "fts query",
        lambda: repo.list_catalog_page(**{**filters, "query": "tema 42"}, sort_by="recent", page_size=160),
        args.iterations,
    )


if __name__ == "__main__":
    main()
