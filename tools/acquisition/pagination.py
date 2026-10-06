"""Technical pagination contracts shared by acquisition and its tests."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_CAPTURE_PAGES = 150
MAX_PAGE_WORKERS = 8
MAX_TOTAL_PAGE_WORKERS = 4


class PageFetchAborted(RuntimeError):
    """A sibling request failed and stopped this category's queued pages."""


def integer(value, field, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    if value < minimum or value != int(value):
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return int(value)


def page_limit(value):
    limit = integer(value, "max_pages", 1)
    if limit > MAX_CAPTURE_PAGES:
        raise ValueError(f"max_pages must be <= {MAX_CAPTURE_PAGES}")
    return limit


def worker_limit(value):
    workers = integer(value, "workers", 1)
    if workers > MAX_PAGE_WORKERS:
        raise ValueError(f"workers must be <= {MAX_PAGE_WORKERS}")
    return workers


def validate_page(payload, requested, expected=None):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Expected an object containing $.data array")
    if any(not isinstance(row, dict) for row in payload["data"]):
        raise ValueError("Every $.data item must be an object")
    metadata = payload.get("metadata")
    pagination = metadata.get("pagination") if isinstance(metadata, dict) else None
    if not isinstance(pagination, dict):
        raise ValueError("Missing $.metadata.pagination object")
    values = {name: integer(pagination.get(name), name)
              for name in ("currentPage", "lastPage", "total", "count")}
    if values["currentPage"] != requested:
        raise ValueError(f"Page mismatch: requested {requested}")
    if values["count"] != len(payload["data"]):
        raise ValueError(f"Row/count mismatch on page {requested}")
    if values["total"] == 0:
        if values["lastPage"] != 0 or values["count"] != 0:
            raise ValueError("Inconsistent empty pagination")
    elif values["lastPage"] < requested or values["count"] == 0:
        raise ValueError("Unexpected empty or out-of-range page")
    if expected and any(values[name] != expected[name] for name in ("lastPage", "total")):
        raise ValueError("Pagination changed during acquisition; retry the whole batch")
    return values


class PaginationTotalMismatch(ValueError):
    def __init__(self, pages, expected, returned, page_limit_reached=False,
                 configured_page_limit=None, metadata_changes=None):
        counts, variants, rows_by_job, category_pairs = {}, {}, {}, set()
        missing = 0
        for page in pages:
            for row in page["response"]["data"]:
                job_no = row.get("jobNo")
                if job_no is None or not str(job_no).strip():
                    missing += 1
                    continue
                key = str(job_no)
                counts[key] = counts.get(key, 0) + 1
                rows_by_job.setdefault(key, []).append(row)
                content = {name: value for name, value in row.items() if name != "pddScore"}
                variants.setdefault(key, set()).add(json.dumps(content, ensure_ascii=False, sort_keys=True))
                categories = row.get("jobCat")
                if isinstance(categories, list):
                    category_pairs.update((key, str(code)) for code in categories)
        conflicting_fields = {}
        for repeated in rows_by_job.values():
            if len(repeated) < 2:
                continue
            for name in {field for candidate in repeated for field in candidate if field != "pddScore"}:
                values = {json.dumps(candidate.get(name), ensure_ascii=False, sort_keys=True)
                          for candidate in repeated}
                if len(values) > 1:
                    conflicting_fields[name] = conflicting_fields.get(name, 0) + 1
        diagnostics = {"returnedRows": returned, "apiTotal": expected["total"],
                       "delta": returned - expected["total"], "pagesFetched": len(pages),
                       "pagesExpected": expected["lastPage"],
                       "pageRowCounts": [len(page["response"]["data"]) for page in pages],
                       "uniqueJobNos": len(counts), "duplicateJobNoRows": sum(n - 1 for n in counts.values()),
                       "conflictingDuplicateJobNos": sum(len(values) > 1 for values in variants.values()),
                       "uniqueJobCategoryAssignments": len(category_pairs),
                       "conflictingFields": conflicting_fields,
                       "rowsMissingJobNo": missing,
                       "pageLimitReached": page_limit_reached,
                       "configuredPageLimit": configured_page_limit,
                       "metadataChanges": metadata_changes or []}
        self.pages, self.diagnostics = pages, diagnostics
        super().__init__(f"Incomplete batch: returned {returned} rows; API total {expected['total']} "
                         f"(delta {returned - expected['total']:+d}, pages {len(pages)}/{expected['lastPage']})")


def collect(fetch, start=1, max_pages=MAX_CAPTURE_PAGES, workers=1):
    start = integer(start, "start", 1)
    max_pages = page_limit(max_pages)
    workers = worker_limit(workers)
    first = fetch(start)
    expected = validate_page(first["response"], start)
    last = expected["lastPage"]
    fetch_last = max(start, min(last, start + max_pages - 1))
    page_limit_reached = last > fetch_last
    page_results = {start: first}
    if workers == 1:
        for page in range(start + 1, fetch_last + 1):
            page_results[page] = fetch(page)
    else:
        with ThreadPoolExecutor(max_workers=workers,
                                thread_name_prefix="104-page") as executor:
            futures = {executor.submit(fetch, page): page
                       for page in range(start + 1, fetch_last + 1)}
            errors = []
            for future in as_completed(futures):
                if future.cancelled():
                    continue
                try:
                    page_results[futures[future]] = future.result()
                except Exception as error:
                    errors.append(error)
                    for pending in futures:
                        if not pending.done():
                            pending.cancel()
            if errors:
                error = errors[0]
                while isinstance(error, PageFetchAborted) and error.__cause__:
                    error = error.__cause__
                raise error
    pages = [page_results[page] for page in range(start, fetch_last + 1)]
    metadata_changes = []
    for page, result in enumerate(pages[1:], start + 1):
        observed = validate_page(result["response"], page)
        changed = {name: {"expected": expected[name], "observed": observed[name]}
                   for name in ("lastPage", "total")
                   if observed[name] != expected[name]}
        if changed:
            metadata_changes.append({"page": page, "values": changed})
    returned = sum(len(page["response"]["data"]) for page in pages)
    page_limit_reached = page_limit_reached or (
        len(pages) == max_pages and returned < expected["total"])
    if (page_limit_reached or (start == 1 and returned != expected["total"])
            or metadata_changes):
        raise PaginationTotalMismatch(pages, expected, returned, page_limit_reached,
                                      max_pages, metadata_changes)
    return pages
