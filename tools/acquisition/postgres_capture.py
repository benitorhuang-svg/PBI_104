"""Build and stream validated category captures into PostgreSQL Bronze."""

from contextlib import contextmanager
from datetime import datetime
import hashlib
from threading import Lock
import uuid
from zoneinfo import ZoneInfo

from .pagination import validate_page
from .postgres_loader import normalize_batch
from .postgres_writer import _save_batch, _save_category_catalog, apply_schema
from .storage import encoded, series_key


def build_batch(request, pages, pagination_status="PASS", diagnostics=None,
                acquired_at=None):
    timestamp = acquired_at or datetime.now(
        ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        raise ValueError("Acquisition timestamp must include a timezone")
    key = series_key(request)
    batch_id = parsed.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    descriptors, capture_pages, raw_rows = [], [], []
    expected = None
    for result in pages:
        page = int(result["response"]["metadata"]["pagination"]["currentPage"])
        values = validate_page(result["response"], page)
        if result.get("technical", {}).get("httpStatus") != 200:
            raise ValueError(f"Page {page} did not return HTTP 200")
        if expected and any(values[name] != expected[name] for name in ("lastPage", "total")):
            if pagination_status != "PAGE_TOTAL_MISMATCH":
                raise ValueError("Pagination metadata changed in a complete batch")
        expected = expected or values
        rows = result["response"]["data"]
        digest = hashlib.sha256(encoded(result)).hexdigest()
        descriptors.append({"page": page, "rows": len(rows), "sha256": digest})
        capture_pages.append({"source_page": page, "response_sha256": digest,
                              "row_count": len(rows),
                              "response_metadata": result["response"]["metadata"],
                              "technical_metadata": result["technical"]})
        raw_rows.extend((page, index, payload) for index, payload in enumerate(rows))
    if not expected or [item["page"] for item in descriptors] != list(range(1, len(pages) + 1)):
        raise ValueError("Capture pages must be a non-empty ordered sequence starting at page 1")
    manifest = {"schemaVersion": 1, "captureStorage": "postgresql-bronze",
                "seriesKey": key, "batchId": batch_id,
                "batchPath": f"postgresql:bronze.capture_batches/{batch_id}",
                "snapshotDate": parsed.date().isoformat(), "snapshotDateTime": timestamp,
                "request": request, "pages": descriptors,
                "rows": sum(item["rows"] for item in descriptors)}
    if pagination_status != "PASS":
        manifest["paginationStatus"] = pagination_status
        manifest["paginationDiagnostics"] = diagnostics
    try:
        jobs = normalize_batch(manifest, raw_rows)
        silver_status, silver_error = "PASS", None
    except (TypeError, ValueError) as error:
        jobs, silver_status, silver_error = [], "BLOCKED", type(error).__name__
    issues = []
    if pagination_status != "PASS":
        issues.append("PAGE_TOTAL_MISMATCH")
    if silver_status != "PASS":
        issues.append("SILVER_NORMALIZATION_BLOCKED")
    capture_status = "_AND_".join(issues) if issues else "COMPLETE"
    return {"manifest": manifest,
            "manifest_sha256": hashlib.sha256(encoded(manifest)).hexdigest(),
            "raw_rows": raw_rows, "jobs": jobs, "capture_pages": capture_pages,
            "silver_status": silver_status, "silver_error_type": silver_error,
            "pagination_status": pagination_status, "capture_status": capture_status}


class DatabaseCaptureError(RuntimeError):
    """A database query or category transaction failed."""


def resume_compatible(manifest, request):
    return manifest.get("seriesKey") == series_key(request)


class CaptureSink:
    def __init__(self, conn, Jsonb):
        self.conn, self.Jsonb = conn, Jsonb
        self.lock = Lock()

    def existing_today(self, request, snapshot_date):
        try:
            with self.lock, self.conn.transaction():
                rows = self.conn.execute("""SELECT batch_id, manifest, row_count, capture_status
                    FROM bronze.capture_batches WHERE snapshot_date = %s AND source_jobcat = %s
                      AND series_key = %s ORDER BY snapshot_datetime DESC""",
                    (snapshot_date, str(request.get("jobcat")), series_key(request))).fetchall()
                return next((row for row in rows
                             if resume_compatible(row[1], request)), None)
        except Exception as error:
            raise DatabaseCaptureError("Database resume lookup failed") from error

    def save(self, batch):
        try:
            with self.lock, self.conn.transaction():
                return _save_batch(self.conn, batch, self.Jsonb)
        except Exception as error:
            diagnostic = getattr(error, "sqlstate", None) or type(error).__name__
            raise DatabaseCaptureError(
                f"Category transaction failed ({diagnostic})") from error


@contextmanager
def open_capture_sink(config, schema_path, category_catalog=None):
    import psycopg
    from psycopg.types.json import Jsonb

    with psycopg.connect(**config) as conn:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended("
                         "'pbi104_schema_initialization', 0))")
            apply_schema(conn, schema_path)
            if category_catalog:
                _save_category_catalog(conn, category_catalog, Jsonb)
        yield CaptureSink(conn, Jsonb)
