"""Capture queued 104 occupation categories in an independent worker process."""

import argparse
from pathlib import Path
import socket
import sys
import threading
import time
import uuid

import psycopg

TOOLS = Path(__file__).resolve().parents[1]
PROJECT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from acquisition.distributed_pacing import (DistributedExponentialBackoff,
                                            DistributedRequestPacer,
                                            DistributedRequestState)
from acquisition.distributed_queue import (claim_next, complete_category,
                                           fail_category, has_unfinished_work,
                                           heartbeat)
from acquisition.distributed_summary import save_distributed_summary
from acquisition.embedded_client import (AccessDeniedError, CategoryRequestStop,
                                         client_code)
from acquisition.pagination import MAX_CAPTURE_PAGES, page_limit
from acquisition.postgres_capture import open_capture_sink
from acquisition.postgres_loader import read_db_config
from capture_category_matrix import capture_target, make_request


SCHEMA_PATH = TOOLS / "sql" / "init_postgres_schema.sql"
DEFAULT_OUTPUT = Path("data/104")


class LeaseHeartbeat:
    def __init__(self, config, run_id, code, worker_id, lease_seconds, interval_seconds):
        self.config = config
        self.run_id = run_id
        self.code = code
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_event.set()
        self.thread.join(timeout=self.interval_seconds + 2)

    def _run(self):
        while not self.stop_event.wait(self.interval_seconds):
            try:
                with psycopg.connect(**self.config) as conn:
                    owned = heartbeat(conn, self.run_id, self.code,
                                      self.worker_id, self.lease_seconds)
                if not owned:
                    print(f"{self.code}: lease is no longer owned by {self.worker_id}", flush=True)
                    return
            except Exception as error:
                print(f"{self.code}: lease heartbeat failed: {type(error).__name__}", flush=True)


def _already_captured(sink, request, category, snapshot_date):
    existing = sink.existing_today(request, snapshot_date)
    if not existing:
        return None
    batch_id, manifest, rows, capture_status = existing
    return {"status": "SKIPPED",
            "code": category["code"], "name": category["name"],
            "seriesKey": manifest["seriesKey"], "batchId": batch_id,
            "rows": rows, "pages": len(manifest.get("pages", [])),
            "captureStatus": capture_status,
            "paginationStatus": manifest.get("paginationStatus", "PASS")}


def _category_result(item, config, sink, output, max_pages,
                     state, compiled_client, worker_id, lease_seconds,
                     heartbeat_seconds):
    (run_id, code, name, _attempts, snapshot_date, _catalog_hash, _depth,
    area, pagesize, minimum_interval, _worker_count) = item
    state.configure(minimum_interval)
    category = {"code": code, "name": name}
    request = make_request(category, area, pagesize)
    existing = _already_captured(sink, request, category, snapshot_date)
    if existing:
        return existing

    pacer = DistributedRequestPacer(state)
    retry_gate = DistributedExponentialBackoff(state)
    stop = CategoryRequestStop()
    try:
        with LeaseHeartbeat(config, run_id, code, worker_id,
                            lease_seconds, heartbeat_seconds):
            result = capture_target(compiled_client, category, request, output,
                                    max_pages, 1, retry_gate, stop, pacer, sink)
        return result
    except AccessDeniedError as error:
        pacer.block(error)
        raise


def run(output, delay=0.8, poll_seconds=5, idle_exit_seconds=30,
        lease_seconds=900, heartbeat_seconds=30, max_pages=MAX_CAPTURE_PAGES):
    config = read_db_config(PROJECT / ".env")
    worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    compiled_client = client_code(PROJECT)
    idle_since = time.monotonic()
    with open_capture_sink(config, SCHEMA_PATH) as sink, psycopg.connect(**config) as queue_conn:
        state = DistributedRequestState(config, minimum_interval=delay)
        try:
            while True:
                item = claim_next(queue_conn, worker_id, lease_seconds)
                if not item:
                    if not has_unfinished_work(queue_conn):
                        return 0
                    if time.monotonic() - idle_since >= idle_exit_seconds:
                        return 0
                    time.sleep(poll_seconds)
                    continue
                idle_since = time.monotonic()
                run_id, code, name = item[:3]
                try:
                    result = _category_result(item, config, sink, output,
                        max_pages, state, compiled_client, worker_id,
                        lease_seconds, heartbeat_seconds)
                    status = complete_category(queue_conn, run_id, code,
                                               worker_id, result, result.get("batchId"))
                except AccessDeniedError as error:
                    result = {"status": "DEFERRED", "code": code, "name": name,
                              "error": str(error)}
                    status = fail_category(queue_conn, run_id, code,
                                           worker_id, result, deferred=True)
                    print(f"{code}: distributed request gate blocked; workers paused",
                          flush=True)
                except Exception as error:
                    result = {"status": "FAIL", "code": code, "name": name,
                              "error": f"{type(error).__name__}: {error}"}
                    status = fail_category(queue_conn, run_id, code,
                                           worker_id, result)
                    print(f"{code}: category failed and will be retried by a later run: "
                          f"{type(error).__name__}: {error}", flush=True)
                summary = save_distributed_summary(queue_conn, run_id, output)
                print(f"[{summary['completedCategories']}/{summary['selectedCategories']} "
                      f"{summary['progressPercent']:.1f}%] {code} "
                      f"{result['status']} | run={status}", flush=True)
                if result["status"] == "DEFERRED":
                    return 1
        finally:
            state.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--idle-exit-seconds", type=float, default=30)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--heartbeat-seconds", type=int, default=30)
    parser.add_argument("--max-pages", type=page_limit, default=MAX_CAPTURE_PAGES)
    args = parser.parse_args(argv)
    if (args.delay < 0 or args.poll_seconds <= 0 or args.idle_exit_seconds < 0
            or args.lease_seconds <= 0 or args.heartbeat_seconds <= 0):
        parser.error("delay must be non-negative and polling/lease timings must be positive")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    return run(output, args.delay, args.poll_seconds, args.idle_exit_seconds,
               args.lease_seconds, args.heartbeat_seconds, args.max_pages)


if __name__ == "__main__":
    raise SystemExit(main())
