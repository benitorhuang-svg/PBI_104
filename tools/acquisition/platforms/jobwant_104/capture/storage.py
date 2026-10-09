"""Publish immutable validated batches, replacing current only after success."""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import uuid

from ..client.pagination import MAX_CAPTURE_PAGES, validate_page


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def series_key(request):
    identity = {key: request[key] for key in ("baseUrl", "area", "jobsource", "mode", "order")}
    for key in ("keyword", "jobcat"):
        value = request.get(key)
        if value is not None and str(value).strip():
            identity[key] = str(value).strip()
    if "keyword" not in identity and "jobcat" not in identity:
        raise ValueError("A capture query needs a keyword or jobcat filter")
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]


def batch_folder(request, key):
    jobcat = request.get("jobcat")
    code = str(jobcat).strip() if jobcat is not None else ""
    if len(code) == 10 and code.isdigit():
        return Path("categories") / code
    return Path("series") / key


def batch_directories(root, request, key):
    folder = batch_folder(request, key)
    directories = [Path(root) / folder / "batches"]
    legacy = Path(root) / "series" / key / "batches"
    if folder.parts[0] == "categories":
        directories.append(legacy)
    return directories


def publish(root, request, pages, acquired_at=None, update_current=True,
            pagination_status="PASS", pagination_diagnostics=None):
    root = Path(root).resolve()
    timestamp = acquired_at or datetime.now().astimezone().isoformat(timespec="seconds")
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        raise ValueError("Acquisition timestamp must include a timezone")
    key = series_key(request)
    batch_id = parsed.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    relative = batch_folder(request, key) / "batches" / batch_id
    batch = root / relative
    category_layout = relative.parts[0] == "categories"
    batch.mkdir(parents=True, exist_ok=False)
    descriptors = []
    for result in pages:
        page = int(result["response"]["metadata"]["pagination"]["currentPage"])
        filename = (f"{parsed:%Y%m%d}_P{page:03d}.json" if category_layout
                    else f"page-{page:05d}.json")
        content = encoded(result)
        (batch / filename).write_bytes(content)
        descriptors.append({"page": page, "file": filename,
                            "rows": len(result["response"]["data"]),
                            "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {"schemaVersion": 1, "seriesKey": key, "batchId": batch_id,
                "batchPath": relative.as_posix(), "snapshotDate": parsed.date().isoformat(),
                "snapshotDateTime": timestamp, "request": request, "pages": descriptors,
                "rows": sum(item["rows"] for item in descriptors)}
    if pagination_status != "PASS":
        manifest["paginationStatus"] = pagination_status
        manifest["paginationDiagnostics"] = pagination_diagnostics
    verify(root, manifest)
    (batch / "manifest.json").write_bytes(encoded(manifest))
    if update_current:
        temporary = root / ("current-" + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(encoded(manifest))
            os.replace(temporary, root / "current.json")
        finally:
            temporary.unlink(missing_ok=True)
    return manifest


def verify(root, manifest):
    root = Path(root).resolve()
    try:
        request = manifest["request"]
        timestamp = datetime.fromisoformat(manifest["snapshotDateTime"])
        batch_id = manifest["batchId"]
        key = manifest["seriesKey"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Manifest identity or timestamp is invalid") from error
    if timestamp.tzinfo is None or manifest.get("schemaVersion") != 1:
        raise ValueError("Manifest needs schema version 1 and a timezone-aware timestamp")
    if timestamp.date().isoformat() != manifest.get("snapshotDate") or series_key(request) != key:
        raise ValueError("Manifest date or series key does not match its request")
    expected_relative = batch_folder(request, key) / "batches" / batch_id
    legacy_relative = Path("series") / key / "batches" / batch_id
    allowed_paths = {expected_relative}
    if expected_relative != legacy_relative and request.get("jobcat") is not None:
        allowed_paths.add(legacy_relative)
    relative = Path(manifest.get("batchPath", ""))
    if relative not in allowed_paths:
        raise ValueError("Batch path does not match its series key and batch ID")
    batch = (root / relative).resolve()
    category_layout = relative.parts[0] == "categories"
    if not batch.is_relative_to(root) or batch == root:
        raise ValueError("Batch path escapes storage root")
    rows = 0
    expected = None
    page_numbers = []
    pagination_status = manifest.get("paginationStatus", "PASS")
    diagnostics = manifest.get("paginationDiagnostics")
    declared_changes = (diagnostics.get("metadataChanges", [])
                        if isinstance(diagnostics, dict) else [])
    metadata_changes = []
    if not isinstance(manifest.get("pages"), list) or not manifest["pages"]:
        raise ValueError("Manifest must contain at least one stored page")
    for page in manifest["pages"]:
        number = page.get("page")
        filename = page.get("file")
        expected_filename = (f"{timestamp:%Y%m%d}_P{number:03d}.json"
                             if category_layout and isinstance(number, int) and not isinstance(number, bool)
                             else f"page-{number:05d}.json")
        if (isinstance(number, bool) or not isinstance(number, int)
                or filename != expected_filename):
            raise ValueError("Page number or filename is invalid")
        path = (batch / filename).resolve()
        if not path.is_relative_to(batch):
            raise ValueError("Page path escapes batch folder")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != page["sha256"]:
            raise ValueError("Batch page checksum mismatch")
        payload = json.loads(content)
        values = validate_page(payload["response"], page["page"])
        changed = ({name: {"expected": expected[name], "observed": values[name]}
                    for name in ("lastPage", "total") if values[name] != expected[name]}
                   if expected else {})
        if changed and pagination_status != "PAGE_TOTAL_MISMATCH":
            raise ValueError("Pagination metadata changed in a complete batch")
        if changed:
            metadata_changes.append({"page": page["page"], "values": changed})
        expected = expected or values
        actual = len(payload["response"]["data"])
        if payload.get("technical", {}).get("httpStatus") != 200:
            raise ValueError("Stored acquisition page did not return HTTP 200")
        if actual != page["rows"]:
            raise ValueError("Manifest row count mismatch")
        rows += actual
        page_numbers.append(page["page"])
    if not expected or rows != manifest["rows"]:
        raise ValueError("Manifest total mismatch")
    if metadata_changes != declared_changes:
        raise ValueError("Pagination-change diagnostics do not match this batch")
    if pagination_status == "PASS" and rows != expected["total"]:
        raise ValueError("Manifest row count does not match the API total")
    if pagination_status == "PAGE_TOTAL_MISMATCH":
        page_limit_reached = (diagnostics.get("pageLimitReached", False)
                              if isinstance(diagnostics, dict) else False)
        if (not isinstance(diagnostics, dict) or not isinstance(page_limit_reached, bool)
                or diagnostics.get("returnedRows") != rows
                or diagnostics.get("apiTotal") != expected["total"]
                or diagnostics.get("delta") != rows - expected["total"]
                or diagnostics.get("pagesFetched") != len(manifest["pages"])
                or diagnostics.get("pagesExpected") != expected["lastPage"]):
            raise ValueError("Explicit API total-mismatch diagnostics do not match this batch")
        if page_limit_reached:
            configured_limit = diagnostics.get("configuredPageLimit")
            if (isinstance(configured_limit, bool) or not isinstance(configured_limit, int)
                    or not 1 <= configured_limit <= MAX_CAPTURE_PAGES
                    or configured_limit != len(manifest["pages"])
                    or not (expected["lastPage"] > len(manifest["pages"])
                            or (expected["lastPage"] == MAX_CAPTURE_PAGES and rows < expected["total"]))):
                raise ValueError("Page-capped batch diagnostics do not match this batch")
        elif rows == expected["total"] and not metadata_changes:
            raise ValueError("Explicit API total-mismatch diagnostics do not match this batch")
    elif pagination_status != "PASS":
        raise ValueError("Unsupported pagination validation status")
    expected_pages = (list(range(1, len(page_numbers) + 1))
                      if pagination_status == "PAGE_TOTAL_MISMATCH"
                      and (manifest["paginationDiagnostics"].get("pageLimitReached", False)
                           or metadata_changes)
                      else list(range(1, max(1, expected["lastPage"]) + 1)))
    if page_numbers != expected_pages:
        raise ValueError("Batch does not contain every page exactly once")
    return rows


def daily_batches(root, manifest):
    directories = batch_directories(root, manifest["request"], manifest["seriesKey"])
    selected = {}
    for directory in directories:
        for path in directory.glob("*/manifest.json"):
            item = json.loads(path.read_text(encoding="utf-8"))
            if item.get("seriesKey") != manifest["seriesKey"]:
                continue
            verify(root, item)
            previous = selected.get(item["snapshotDate"])
            item_order = (datetime.fromisoformat(item["snapshotDateTime"]), item["batchId"])
            previous_order = ((datetime.fromisoformat(previous["snapshotDateTime"]), previous["batchId"])
                              if previous else None)
            if previous is None or item_order > previous_order:
                selected[item["snapshotDate"]] = item
    return [selected[day] for day in sorted(selected)]
