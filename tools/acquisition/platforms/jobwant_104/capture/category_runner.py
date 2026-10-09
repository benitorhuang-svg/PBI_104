"""Run independent category captures with bounded category-level concurrency."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from ..client.embedded_client import AccessDeniedError
from ..client.pagination import PageFetchAborted
from ..persistence.capture import DatabaseCaptureError


def process_categories(targets, request_for, capture_one, inspect_one, find_existing,
                       capture, resume, request_stop, worker_count, on_complete):
    def worker(index, category):
        try:
            request_stop.check()
            request = request_for(category)
            existing = find_existing(category, request) if capture and resume else None
            if existing:
                result = existing
            elif capture:
                result = capture_one(category, request, request_stop)
            else:
                result = inspect_one(category, request)
                result["name"] = category["name"]
                result["totalPages"] = result["pagination"]["lastPage"]
                result["totalJobs"] = result["pagination"]["total"]
            return result, None
        except Exception as error:
            deferred = isinstance(error, PageFetchAborted)
            if not deferred:
                request_stop.stop(error)
            result = {"status": "DEFERRED" if deferred else "FAIL",
                      "code": category["code"], "name": category["name"],
                      "error": str(error),
                      "httpCalls": getattr(error, "http_calls", 0),
                      "retryAttempts": getattr(error, "retry_attempts", 0),
                      "backoffSeconds": getattr(error, "backoff_seconds", 0)}
            if hasattr(error, "diagnostics"):
                result["paginationDiagnostics"] = error.diagnostics
            if isinstance(error, AccessDeniedError):
                halt = "BLOCKED"
            elif isinstance(error, DatabaseCaptureError):
                halt = "DATABASE_ERROR"
            else:
                halt = None if deferred else "PAUSED_ERROR"
            return result, halt

    return run_parallel(targets, worker, worker_count, on_complete)


def run_parallel(targets, worker, worker_count, on_complete):
    results = [None] * len(targets)
    halt_status = None
    with ThreadPoolExecutor(max_workers=worker_count,
                            thread_name_prefix="104-category") as executor:
        futures = {executor.submit(worker, index, category): index
                   for index, category in enumerate(targets)}
        for future in as_completed(futures):
            index = futures[future]
            result, halt = future.result()
            results[index] = result
            halt_status = halt_status or halt
            on_complete(index, result, results)
    return results, halt_status
