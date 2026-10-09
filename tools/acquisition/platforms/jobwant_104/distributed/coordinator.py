"""Queue the official 104 occupation taxonomy for PostgreSQL-backed workers."""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import uuid
from zoneinfo import ZoneInfo

TOOLS = Path(__file__).resolve().parents[3]
PROJECT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from ..capture.category_catalog import (
    fetch_official_catalog, read_latest_catalog, write_catalog_snapshot)
from .queue import register_run, run_progress
from .summary import save_distributed_summary
from ..persistence.capture import open_capture_sink
from ..persistence.loader import read_db_config
from ..capture.storage import series_key
from ..capture.capture_category_matrix import make_request


SCHEMA_PATH = TOOLS / "sql" / "init_postgres_schema.sql"
DEFAULT_OUTPUT = Path("data/104")


def _status(output, run_id=None):
    import psycopg

    config = read_db_config(PROJECT / ".env")
    with psycopg.connect(**config) as conn:
        progress = run_progress(conn, run_id)
        if not progress:
            print(json.dumps({"status": "NO_RUN"}))
            return 1
        summary = save_distributed_summary(conn, progress["runId"], output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def enqueue(output, depth, area, pagesize, delay, workers):
    config = read_db_config(PROJECT / ".env")
    try:
        fetched = fetch_official_catalog()
    except Exception as error:
        saved = read_latest_catalog(output)
        if not saved:
            raise
        print("Official catalogue fetch failed; using the last checksum-verified "
              f"snapshot ({type(error).__name__}).", file=sys.stderr, flush=True)
    else:
        saved = write_catalog_snapshot(output, fetched)
    catalog_hash = saved["manifest"]["sha256"]
    categories = [row for row in saved["rows"] if row["depth"] == depth]
    if not categories:
        raise ValueError(f"No official occupation categories at depth {depth}")
    first_request = make_request(categories[0], area, pagesize)
    snapshot_date = datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    run_scope = {"snapshotDate": snapshot_date, "catalogSha256": catalog_hash,
                 "depth": depth, "area": area, "seriesKey": series_key(first_request)}
    run_key = hashlib.sha256(json.dumps(run_scope, sort_keys=True).encode("utf-8")).hexdigest()
    run_id = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z") + "-" + uuid.uuid4().hex[:8]
    run = {"runId": run_id, "runKey": run_key, "snapshotDate": snapshot_date,
           "catalogSha256": catalog_hash, "depth": depth, "area": area,
           "pagesize": pagesize, "delay": delay, "workerCount": workers}
    with open_capture_sink(config, SCHEMA_PATH, saved) as sink:
        actual_run_id = register_run(sink.conn, run, categories)
        summary = save_distributed_summary(sink.conn, actual_run_id, output)
    print(json.dumps({"queuedRunId": actual_run_id, "status": summary["status"],
                      "selectedCategories": summary["selectedCategories"],
                      "completedCategories": summary["completedCategories"],
                      "catalogSha256": catalog_hash}, ensure_ascii=False, indent=2))
    return actual_run_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--depth", type=int, choices=(0, 1, 2), default=2)
    parser.add_argument("--area", default=None)
    parser.add_argument("--pagesize", type=int, choices=range(1, 31), default=30)
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    if args.delay < 0 or args.workers < 1:
        parser.error("--delay must be non-negative and --workers must be positive")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.status:
        return _status(output, args.run_id)
    enqueue(output, args.depth, args.area or None, args.pagesize, args.delay, args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
