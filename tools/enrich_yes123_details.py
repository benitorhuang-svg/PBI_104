"""Concurrent operator entry point for enriching yes123 job details and geocodes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any, Dict, List, Optional

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import psycopg
import requests
from acquisition.platforms.jobwant_104.persistence.loader import read_db_config
from acquisition.platforms.yes123.enricher import (
    ensure_enrichment_schema,
    enrich_single_job,
    persist_enrichment,
)


def run_enrichment(
    limit: Optional[int] = None,
    workers: int = 4,
    dbname: str = "jobwant_yes123",
    env_file: Path = Path(".env"),
) -> Dict[str, Any]:
    """Execute multi-threaded enrichment across all pending yes123 jobs."""
    db_config = read_db_config(env_file)
    db_config["dbname"] = dbname

    with psycopg.connect(**db_config) as conn:
        with conn.transaction():
            ensure_enrichment_schema(conn)

        query = """
            SELECT j.job_no, j.job_link, j.source_area
            FROM silver.job_current j
            LEFT JOIN silver.job_detail_enrichments e ON j.job_no = e.job_no
            WHERE e.job_no IS NULL
            ORDER BY j.job_no
        """
        if limit is not None and limit > 0:
            query += f" LIMIT {limit}"

        with conn.cursor() as cur:
            cur.execute(query)
            pending_rows = [
                {"job_no": r[0], "job_link": r[1], "source_area": r[2]}
                for r in cur.fetchall()
            ]

    total_pending = len(pending_rows)
    print(f"Total pending jobs to enrich: {total_pending} (Concurrency: {workers} workers)")
    if total_pending == 0:
        print("All jobs have already been enriched. No work required.")
        return {"status": "ALL_COMPLETED", "total": 0}

    work_q: queue.Queue = queue.Queue()
    for row in pending_rows:
        work_q.put(row)

    print_lock = threading.Lock()
    stats_lock = threading.Lock()
    processed = 0
    stats = {"LOCAL_GEOCODER": 0, "GOOGLE_MAPS_EMBED_FALLBACK": 0, "OVERSEAS": 0, "NOT_FOUND": 0}
    t0 = time.monotonic()

    def worker_loop(wid: int) -> None:
        nonlocal processed
        session = requests.Session()
        with psycopg.connect(**db_config) as conn:
            while True:
                try:
                    job_row = work_q.get_nowait()
                except queue.Empty:
                    break

                jno = job_row["job_no"]
                try:
                    res = enrich_single_job(job_row, session)
                    with conn.transaction():
                        persist_enrichment(conn, res)

                    strat = res["strategy"]
                    with stats_lock:
                        processed += 1
                        curr_cnt = processed
                        if res["latitude"] is not None:
                            if res["is_overseas"]:
                                stats["OVERSEAS"] += 1
                            elif strat in stats:
                                stats[strat] += 1
                            else:
                                stats["GOOGLE_MAPS_EMBED_FALLBACK"] += 1
                        else:
                            stats["NOT_FOUND"] += 1

                    if curr_cnt % 10 == 0 or curr_cnt == total_pending:
                        pct = (curr_cnt / total_pending) * 100
                        elapsed = time.monotonic() - t0
                        speed = curr_cnt / elapsed if elapsed > 0 else 0.0
                        with print_lock:
                            print(
                                f"[{curr_cnt}/{total_pending}] ({pct:5.1f}%) "
                                f"Speed: {speed:4.1f} jobs/s | "
                                f"Local: {stats['LOCAL_GEOCODER']}, "
                                f"GMaps: {stats['GOOGLE_MAPS_EMBED_FALLBACK']}, "
                                f"Overseas: {stats['OVERSEAS']}, "
                                f"NotFound: {stats['NOT_FOUND']}"
                            )
                except Exception as err:
                    with print_lock:
                        print(f"[W{wid}] Error enriching {jno}: {err}")
                finally:
                    work_q.task_done()

    threads = []
    num_threads = min(workers, total_pending)
    for w in range(1, num_threads + 1):
        t = threading.Thread(target=worker_loop, args=(w,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    total_time = round(time.monotonic() - t0, 2)
    print("=" * 80)
    print(f"Enrichment completed in {total_time}s across {num_threads} workers.")
    print(f"Processed: {processed}/{total_pending} | Stats: {stats}")
    print("=" * 80)
    return {"processed": processed, "stats": stats, "elapsed": total_time}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of jobs to enrich in this run")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of concurrent enrichment workers (default: 4)")
    parser.add_argument("--dbname", type=str, default="jobwant_yes123",
                        help="Target PostgreSQL database (default: jobwant_yes123)")
    parser.add_argument("--env-file", type=Path, default=Path(".env"),
                        help="Path to environment configuration file")
    args = parser.parse_args(argv)

    try:
        run_enrichment(
            limit=args.limit,
            workers=args.workers,
            dbname=args.dbname,
            env_file=args.env_file,
        )
        return 0
    except Exception as exc:
        print(f"Fatal enrichment error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
