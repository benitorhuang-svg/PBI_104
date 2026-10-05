"""Publish immutable validated batches, replacing current only after success."""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import uuid

from .pagination import validate_page


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def series_key(request):
    identity = {key: request[key] for key in ("baseUrl", "keyword", "area", "jobsource", "mode", "order")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]


def publish(root, request, pages, acquired_at=None):
    root = Path(root).resolve()
    timestamp = acquired_at or datetime.now().astimezone().isoformat(timespec="seconds")
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        raise ValueError("Acquisition timestamp must include a timezone")
    key = series_key(request)
    batch_id = parsed.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    relative = Path("series") / key / "batches" / batch_id
    batch = root / relative
    batch.mkdir(parents=True, exist_ok=False)
    descriptors = []
    for result in pages:
        page = int(result["response"]["metadata"]["pagination"]["currentPage"])
        filename = f"page-{page:05d}.json"
        content = encoded(result)
        (batch / filename).write_bytes(content)
        descriptors.append({"page": page, "file": filename,
                            "rows": len(result["response"]["data"]),
                            "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {"schemaVersion": 1, "seriesKey": key, "batchId": batch_id,
                "batchPath": relative.as_posix(), "snapshotDate": parsed.date().isoformat(),
                "snapshotDateTime": timestamp, "request": request, "pages": descriptors,
                "rows": sum(item["rows"] for item in descriptors)}
    verify(root, manifest)
    (batch / "manifest.json").write_bytes(encoded(manifest))
    temporary = root / ("current-" + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(encoded(manifest))
        os.replace(temporary, root / "current.json")
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


def verify(root, manifest):
    root = Path(root).resolve()
    batch = (root / manifest["batchPath"]).resolve()
    if not batch.is_relative_to(root) or batch == root:
        raise ValueError("Batch path escapes storage root")
    rows = 0
    expected = None
    page_numbers = []
    for page in manifest["pages"]:
        path = (batch / page["file"]).resolve()
        if not path.is_relative_to(batch):
            raise ValueError("Page path escapes batch folder")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != page["sha256"]:
            raise ValueError("Batch page checksum mismatch")
        payload = json.loads(content)
        values = validate_page(payload["response"], page["page"], expected)
        expected = expected or values
        actual = len(payload["response"]["data"])
        if actual != page["rows"]:
            raise ValueError("Manifest row count mismatch")
        rows += actual
        page_numbers.append(page["page"])
    if not expected or rows != manifest["rows"] or rows != expected["total"]:
        raise ValueError("Manifest total mismatch")
    if page_numbers != list(range(1, max(1, expected["lastPage"]) + 1)):
        raise ValueError("Batch does not contain every page exactly once")
    return rows


def daily_batches(root, manifest):
    directory = Path(root) / "series" / manifest["seriesKey"] / "batches"
    selected = {}
    for path in directory.glob("*/manifest.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        verify(root, item)
        previous = selected.get(item["snapshotDate"])
        if previous is None or (item["snapshotDateTime"], item["batchId"]) > (previous["snapshotDateTime"], previous["batchId"]):
            selected[item["snapshotDate"]] = item
    return [selected[day] for day in sorted(selected)]
