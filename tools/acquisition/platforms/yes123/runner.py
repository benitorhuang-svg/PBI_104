"""Batch category acquisition runner for yes123 with adaptive annealing and concurrent DB persistence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

TOOLS = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TOOLS))

from .annealer import AnnealingPacer
from .catalog import fetch_work_mode_catalog, get_completed_category_codes, seed_categories_to_crosswalk
from .client import Yes123Client
from .loader import save_yes123_batch
from ..jobwant_104.persistence.loader import read_db_config


def run_catalog_acquisition(
    limit: Optional[int] = None,
    max_pages: Optional[int] = None,
    force: bool = False,
    env_file: Path = Path(".env"),
    min_interval: float = 0.5,
    workers: int = 3,
    dbname: str = "jobwant_yes123",
) -> Dict[str, Any]:
    """Execute concurrent catalog run across all yes123 work mode categories."""
    db_config = read_db_config(env_file)
    db_config["dbname"] = dbname
    import psycopg
    from psycopg.types.json import Jsonb

    print(f"Fetching official yes123 work_mode.json catalog (Concurrency: {workers} workers, min_interval: {min_interval}s)...")
    catalog = fetch_work_mode_catalog()
    total_in_catalog = len(catalog)

    with psycopg.connect(**db_config) as conn:
        with conn.transaction():
            seeded = seed_categories_to_crosswalk(conn, catalog)
        completed_today = get_completed_category_codes(conn)

    print(f"Registered {seeded} categories to crosswalk. Already completed today: {len(completed_today)} / {total_in_catalog}.")

    pending = [c for c in catalog if force or c["code"] not in completed_today]
    if limit is not None and limit > 0:
        pending = pending[:limit]

    print(f"Categories to process in this run: {len(pending)} (Already finished: {len(completed_today)}).")
    if not pending:
        print("All categories have already been captured today. Use --force to re-acquire.")
        return {"status": "ALL_COMPLETED", "total": total_in_catalog, "processed": 0}

    print_lock = threading.Lock()
    stats_lock = threading.Lock()
    processed_count = 0
    total_jobs_ingested = 0
    started_at = time.monotonic()
    total_pending = len(pending)

    def process_category(cat: Dict[str, Any], worker_id: int) -> Tuple[int, int]:
        nonlocal processed_count, total_jobs_ingested
        code = cat["code"]
        name = cat["name"]
        group = cat["group_name"]

        pacer = AnnealingPacer(min_interval=min_interval, initial_interval=max(0.8, min_interval))
        client = Yes123Client(pacer=pacer)

        try:
            batch = client.collect(category_code=code, max_pages=max_pages)
            with psycopg.connect(**db_config) as conn:
                with conn.transaction():
                    ingest_summary = save_yes123_batch(conn, batch, Jsonb)

            jobs_count = len(batch["jobs"])
            with stats_lock:
                processed_count += 1
                total_jobs_ingested += jobs_count
                curr_idx = processed_count
                curr_pct = (curr_idx / total_pending) * 100

            with print_lock:
                print(
                    f"[W{worker_id}] [{curr_idx}/{total_pending}] ({curr_pct:4.1f}%) "
                    f"Code: {code} ({name} | {group}) -> Jobs: {jobs_count} (Reported: {batch['reported_total']}) | "
                    f"Silver: {ingest_summary['jobs']}"
                )
            return (1, jobs_count)
        except Exception as exc:
            with print_lock:
                print(f"[W{worker_id}] FAIL on {code} ({name}): {type(exc).__name__}: {exc}")
            return (0, 0)

    work_queue: queue.Queue = queue.Queue()
    for item in pending:
        work_queue.put(item)

    def worker_loop(wid: int) -> None:
        while True:
            try:
                cat = work_queue.get_nowait()
            except queue.Empty:
                break
            process_category(cat, wid)
            work_queue.task_done()

    threads = []
    effective_workers = min(workers, total_pending)
    for w in range(1, effective_workers + 1):
        t = threading.Thread(target=worker_loop, args=(w,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    elapsed = round(time.monotonic() - started_at, 2)
    summary = {
        "status": "COMPLETED",
        "total_catalog": total_in_catalog,
        "processed_categories": processed_count,
        "total_jobs_ingested": total_jobs_ingested,
        "elapsed_seconds": elapsed,
        "effective_workers": effective_workers,
    }
    print("=" * 80)
    print(f"High-throughput run completed in {elapsed}s: {processed_count} categories, {total_jobs_ingested} jobs ingested across {effective_workers} workers.")
    print("=" * 80)
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of categories to process in this run")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Maximum pages to fetch per category")
    parser.add_argument("--force", action="store_true",
                        help="Force re-acquisition of already captured categories today")
    parser.add_argument("--min-interval", type=float, default=0.5,
                        help="Minimum pacing interval in seconds (default: 0.5)")
    parser.add_argument("--workers", type=int, default=3,
                        help="Number of concurrent acquisition workers (default: 3)")
    parser.add_argument("--dbname", type=str, default="jobwant_yes123",
                        help="Target PostgreSQL database name (default: jobwant_yes123)")
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="Path to environment configuration file")
    args = parser.parse_args(argv)

    try:
        run_catalog_acquisition(
            limit=args.limit,
            max_pages=args.max_pages,
            force=args.force,
            env_file=args.env_file,
            min_interval=args.min_interval,
            workers=args.workers,
            dbname=args.dbname,
        )
        return 0
    except Exception as err:
        print(f"Fatal run error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
