"""Inspect or capture 104 jobs by its official top-level occupational categories."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from threading import Lock
import time
import uuid

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from acquisition.category_catalog import fetch_official_catalog, write_catalog_snapshot
from acquisition.category_run_storage import completed_today, save_run
from acquisition.embedded_client import (CategoryRequestStop, ExponentialBackoff, RequestPacer,
                                         client_code, fetch_page, fetch_page_with_backoff)
from acquisition.category_runner import process_categories
from acquisition.pagination import (MAX_CAPTURE_PAGES, MAX_TOTAL_PAGE_WORKERS,
                                    PaginationTotalMismatch, collect, integer,
                                    page_limit, validate_page, worker_limit)
from acquisition.postgres_capture import build_batch, open_capture_sink
from acquisition.postgres_loader import read_db_config
from acquisition.storage import publish

BASE_URL = "https://www.104.com.tw/jobs/search/api/jobs"
DEFAULT_AREA = None


def category_targets(rows, codes=None, depth=0):
    categories = [row for row in rows if row["depth"] == depth]
    by_code = {row["code"]: row for row in categories}
    selected = list(codes) if codes else list(by_code)
    unknown = sorted(set(selected) - set(by_code))
    if unknown:
        raise ValueError(f"Codes must match official categories at depth {depth}: {unknown}")
    if len(selected) != len(set(selected)):
        raise ValueError("Category codes must be unique")
    return [by_code[code] for code in selected]


def make_request(category, area, pagesize):
    return {"baseUrl": BASE_URL, "jobcat": category["code"], "area": area,
            "jobsource": "index_s", "mode": "s", "order": "15", "page": 1,
            "pagesize": integer(pagesize, "pagesize", 1)}


def inspect_target(code, target):
    response = fetch_page(code, target, 1)
    pagination = validate_page(response["response"], 1)
    rows = response["response"]["data"]
    job_numbers = [str(row["jobNo"]) for row in rows
                   if row.get("jobNo") is not None and str(row["jobNo"]).strip()]
    return {"status": "INSPECTED", "code": target["jobcat"],
            "pagination": pagination, "httpStatus": response["technical"]["httpStatus"],
            "rowsReturned": len(rows), "uniqueJobNos": len(set(job_numbers)),
            "duplicateJobNoRows": len(job_numbers) - len(set(job_numbers)),
            "rowsMissingJobNo": len(rows) - len(job_numbers)}


def capture_target(code, category, target, output_dir, max_pages, workers,
                   retry_gate, request_stop, request_pacer, sink=None):
    calls = 0
    calls_lock = Lock()
    retry_attempts = 0
    backoff_seconds = 0.0
    retry_lock = Lock()

    def request_once(page):
        nonlocal calls
        with calls_lock:
            calls += 1
            call_number = calls
        request_pacer.wait()
        while retry_gate.wait(request_stop):
            request_pacer.wait()
        if call_number % 10 == 0:
            print(f"  {target['jobcat']} request attempt {call_number}", flush=True)
        response = fetch_page(code, target, page)
        request_pacer.succeeded()
        return response

    def on_retry(page, attempt, wait_seconds, reason):
        nonlocal retry_attempts, backoff_seconds
        with retry_lock:
            retry_attempts += 1
            backoff_seconds += wait_seconds
        label = f"HTTP {reason}" if isinstance(reason, int) else str(reason)
        if reason == 429:
            interval = request_pacer.backoff(wait_seconds)
            label += f"; global interval {interval:.1f}s"
        print(f"  {target['jobcat']} page {page}: {label}; retry {attempt} "
              f"after {wait_seconds:.1f}s", flush=True)

    def fetch(page):
        return fetch_page_with_backoff(
            lambda: request_once(page), page, retry_gate, request_stop, on_retry)

    started = time.monotonic()
    pagination_status, diagnostics = "PASS", None
    try:
        pages = collect(fetch, max_pages=max_pages, workers=workers)
    except PaginationTotalMismatch as error:
        pages = error.pages
        pagination_status, diagnostics = "PAGE_TOTAL_MISMATCH", error.diagnostics
    except Exception as error:
        request_stop.stop(error)
        error.http_calls = calls
        error.retry_attempts = retry_attempts
        error.backoff_seconds = round(backoff_seconds, 2)
        raise
    batch = None
    if sink:
        batch = build_batch(target, pages, pagination_status, diagnostics)
        sink.save(batch)
        manifest = batch["manifest"]
    else:
        manifest = publish(output_dir, target, pages, update_current=False,
                           pagination_status=pagination_status,
                           pagination_diagnostics=diagnostics)
    warning = pagination_status != "PASS" or (batch and batch["capture_status"] != "COMPLETE")
    result = {"status": "CAPTURED_WITH_WARNING" if warning else "CAPTURED",
            "paginationStatus": pagination_status, "paginationDiagnostics": diagnostics,
            "code": category["code"], "name": category["name"],
            "seriesKey": manifest["seriesKey"], "batchId": manifest["batchId"],
            "rows": manifest["rows"], "pages": len(pages), "httpCalls": calls,
            "pageWorkers": workers, "retryAttempts": retry_attempts,
            "backoffSeconds": round(backoff_seconds, 2),
            "seconds": round(time.monotonic() - started, 2)}
    if batch:
        result["captureStatus"] = batch["capture_status"]
        result["silverStatus"] = batch["silver_status"]
    return result


def run(output, area=DEFAULT_AREA, pagesize=30, delay=0.8, codes=None,
        capture=False, max_pages=MAX_CAPTURE_PAGES, resume=False, depth=0,
        workers=2, direct_postgres=False, category_workers=2):
    max_pages = page_limit(max_pages)
    workers = worker_limit(workers)
    category_workers = integer(category_workers, "category_workers", 1)
    if (category_workers > MAX_TOTAL_PAGE_WORKERS
            or workers * category_workers > MAX_TOTAL_PAGE_WORKERS):
        raise ValueError(f"workers * category_workers must be <= {MAX_TOTAL_PAGE_WORKERS}")
    if direct_postgres and not capture:
        raise ValueError("--direct-postgres requires --capture")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    fetched = fetch_official_catalog()
    saved_catalog = write_catalog_snapshot(output, fetched)
    targets = category_targets(saved_catalog["rows"], codes, depth)
    project = TOOLS.parent
    code = client_code(project)
    results = []
    run_id = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z") + "-" + uuid.uuid4().hex[:8]
    summary = {"schemaVersion": 1, "mode": "capture" if capture else "inspect",
               "status": "RUNNING", "runId": run_id,
               "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
               "catalogSha256": saved_catalog["manifest"]["sha256"],
               "officialCategoryCount": len([r for r in saved_catalog["rows"] if r["depth"] == depth]),
               "categoryDepth": depth,
               "selectedCategories": len(targets), "area": area, "pagesize": pagesize,
               "storage": "postgresql-bronze" if direct_postgres else "json-lake",
               "pageWorkersPerCategory": workers, "categoryWorkers": category_workers,
               "requestIntervalSeconds": delay,
               "successfulCategories": 0, "warningCategories": 0,
               "totalJobs": 0, "retryAttempts": 0,
               "backoffSeconds": 0, "categories": results}
    save_run(output, run_id, summary)

    sink_context = None
    sink = None
    if direct_postgres:
        config = read_db_config(project / ".env")
        sink_context = open_capture_sink(
            config, project / "tools/sql/init_postgres_schema.sql", saved_catalog)
        sink = sink_context.__enter__()
    try:
        retry_gate = ExponentialBackoff()
        request_stop = CategoryRequestStop()
        request_pacer = RequestPacer(delay)

        def capture_one(category, request, stop):
            return capture_target(code, category, request, output, max_pages,
                                  workers, retry_gate, stop, request_pacer, sink)

        def find_existing(category, request):
            today = datetime.now().astimezone().date().isoformat()
            existing = (sink.existing_today(request, today) if sink
                        else completed_today(output, request))
            if not existing:
                return None
            if sink:
                manifest = existing[1]
                return {"status": "SKIPPED", "code": category["code"],
                        "name": category["name"], "seriesKey": manifest["seriesKey"],
                        "batchId": existing[0], "rows": existing[2],
                        "pages": len(manifest["pages"])}
            return {"status": "SKIPPED", "code": category["code"],
                    "name": category["name"], "seriesKey": existing["seriesKey"],
                    "batchId": existing["batchId"], "rows": existing["rows"],
                    "pages": len(existing["pages"])}

        def on_complete(index, result, completed):
            done = [item for item in completed if item is not None]
            summary["requestIntervalSeconds"] = round(request_pacer.interval_seconds, 2)
            summary["successfulCategories"] = sum(r["status"] in
                ("CAPTURED", "CAPTURED_WITH_WARNING", "INSPECTED", "SKIPPED") for r in done)
            summary["warningCategories"] = sum(r["status"] == "CAPTURED_WITH_WARNING" for r in done)
            summary["totalJobs"] = sum(r.get("totalJobs", r.get("rows", 0)) for r in done)
            summary["retryAttempts"] = sum(r.get("retryAttempts", 0) for r in done)
            summary["backoffSeconds"] = round(sum(r.get("backoffSeconds", 0) for r in done), 2)
            summary["categories"] = done
            save_run(output, run_id, summary)
            metric = result.get("totalJobs", result.get("rows", 0))
            print(f"[{index + 1}/{len(targets)}] {result['code']} {result['status']} {metric} jobs", flush=True)

        results, halt_status = process_categories(
            targets, lambda category: make_request(category, area, pagesize),
            capture_one, inspect_target, find_existing, capture, resume,
            request_stop, category_workers, on_complete)

        if halt_status:
            summary["status"] = halt_status
        elif summary["successfulCategories"] != summary["selectedCategories"]:
            summary["status"] = "PARTIAL"
        elif summary["warningCategories"]:
            summary["status"] = "COMPLETE_WITH_WARNINGS"
        else:
            summary["status"] = "COMPLETE"
        save_run(output, run_id, summary)
        return summary
    finally:
        if sink_context:
            sink_context.__exit__(*sys.exc_info())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/104"))
    parser.add_argument("--area", default=DEFAULT_AREA,
                        help="Optional area filter; omitted or empty means all areas")
    parser.add_argument("--pagesize", type=int, default=30, help="Verified maximum: 30")
    parser.add_argument("--delay", type=float, default=0.8, help="Minimum global request interval in seconds")
    parser.add_argument("--max-pages", type=page_limit, default=MAX_CAPTURE_PAGES)
    parser.add_argument("--workers", type=int,
                        choices=range(1, MAX_TOTAL_PAGE_WORKERS + 1), default=2,
                        help=f"Concurrent page requests per category (1-{MAX_TOTAL_PAGE_WORKERS}; default: 2)")
    parser.add_argument("--category-workers", type=int,
                        choices=range(1, MAX_TOTAL_PAGE_WORKERS + 1), default=2,
                        help="Concurrent categories; combined page workers are capped at 4")
    parser.add_argument("--code", action="append", dest="codes",
                        help="Inspect/capture one category at the selected depth; repeatable")
    parser.add_argument("--depth", type=int, choices=(0, 1, 2), default=0,
                        help="Official taxonomy depth: 0 top-level, 1 subcategory, 2 occupation")
    parser.add_argument("--capture", action="store_true",
                        help="Capture every page as immutable category batches without changing current.json")
    parser.add_argument("--direct-postgres", action="store_true",
                        help="With --capture, store the verified batch directly in PostgreSQL Bronze")
    parser.add_argument("--resume", action="store_true",
                        help="With --capture, skip complete or page-capped batches already captured today")
    args = parser.parse_args(argv)
    if (args.resume or args.direct_postgres) and not args.capture:
        parser.error("--resume and --direct-postgres require --capture")
    try:
        summary = run(args.output, args.area or None, args.pagesize, args.delay,
                      args.codes, args.capture, args.max_pages, args.resume,
                      args.depth, args.workers, args.direct_postgres,
                      args.category_workers)
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["successfulCategories"] == summary["selectedCategories"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
