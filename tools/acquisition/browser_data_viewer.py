"""Serve a loopback-only, read-only browser for committed 104 capture data."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

TOOLS = Path(__file__).resolve().parents[1]
PROJECT = TOOLS.parent
ASSETS = Path(__file__).with_name("browser_viewer")
sys.path.insert(0, str(TOOLS))

from acquisition.postgres_loader import read_db_config

ASSET_TYPES = {"/": "text/html; charset=utf-8",
               "/viewer.css": "text/css; charset=utf-8",
               "/viewer.js": "text/javascript; charset=utf-8"}
QUEUE_STATES = {"PENDING", "LEASED", "DONE", "FAIL", "DEFERRED"}
PAGE_SIZE = 50
JOB_PAGE_SIZE = 20
DB_CONFIG = read_db_config(PROJECT / ".env")


@contextmanager
def readonly_connection():
    import psycopg

    with psycopg.connect(**DB_CONFIG,
                         options="-c default_transaction_read_only=on") as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        yield conn


def latest_run(conn):
    return conn.execute("""SELECT run_id, status, snapshot_date::text,
        selected_categories, category_depth, area_filter, pagesize,
        started_at, updated_at
        FROM bronze.distributed_capture_runs ORDER BY created_at DESC LIMIT 1""").fetchone()


def fetch_status(conn):
    run = latest_run(conn)
    if not run:
        return {"status": "NO_RUN", "selectedCategories": 0}
    counts = dict(conn.execute("""SELECT state, COUNT(*)
        FROM bronze.distributed_capture_categories WHERE run_id = %s GROUP BY state""",
        (run[0],)).fetchall())
    result_counts = dict(conn.execute("""SELECT result->>'status', COUNT(*)
        FROM bronze.distributed_capture_categories
        WHERE run_id = %s AND state = 'DONE' GROUP BY result->>'status'""",
        (run[0],)).fetchall())
    gate = conn.execute("""SELECT minimum_interval_seconds, interval_seconds,
        blocked_reason, updated_at FROM bronze.capture_request_state
        WHERE channel = '104_jobs'""").fetchone()
    done = counts.get("DONE", 0)
    return {
        "runId": run[0], "status": run[1], "snapshotDate": run[2],
        "selectedCategories": run[3], "categoryDepth": run[4],
        "area": run[5], "pageSize": run[6], "startedAt": run[7],
        "updatedAt": run[8], "completedCategories": done,
        "capturedCategories": (result_counts.get("CAPTURED", 0)
                               + result_counts.get("CAPTURED_WITH_WARNING", 0)),
        "warningCategories": result_counts.get("CAPTURED_WITH_WARNING", 0),
        "skippedCategories": result_counts.get("SKIPPED", 0),
        "runningCategories": counts.get("LEASED", 0),
        "pendingCategories": counts.get("PENDING", 0),
        "failedCategories": counts.get("FAIL", 0),
        "deferredCategories": counts.get("DEFERRED", 0),
        "progressPercent": round(100 * done / run[3], 1) if run[3] else 100.0,
        "minimumIntervalSeconds": round(gate[0], 2) if gate else None,
        "intervalSeconds": round(gate[1], 2) if gate else None,
        "gateBlocked": bool(gate and gate[2]),
        "gateUpdatedAt": gate[3] if gate else None,
    }


def page_number(params):
    try:
        page = int(params.get("page", ["1"])[0])
    except ValueError as error:
        raise ValueError("page must be a positive integer") from error
    if not 1 <= page <= 10000:
        raise ValueError("page must be between 1 and 10000")
    return page


def fetch_categories(conn, params):
    run = latest_run(conn)
    if not run:
        return {"runId": None, "total": 0, "page": 1,
                "pageSize": PAGE_SIZE, "categories": []}
    search = params.get("search", [""])[0].strip()[:120]
    state = params.get("state", [""])[0].upper()
    if state and state not in QUEUE_STATES:
        raise ValueError("Unknown queue state")
    page = page_number(params)
    filters = ["q.run_id = %s"]
    values = [run[0]]
    if search:
        filters.append("(q.source_jobcat ILIKE %s OR q.category_name ILIKE %s)")
        values.extend([f"%{search}%", f"%{search}%"])
    if state:
        filters.append("q.state = %s")
        values.append(state)
    where = " AND ".join(filters)
    total = conn.execute(f"""SELECT COUNT(*)
        FROM bronze.distributed_capture_categories q WHERE {where}""",
        values).fetchone()[0]
    rows = conn.execute(f"""SELECT q.source_jobcat, q.category_name, q.state,
        q.attempts, q.updated_at, b.batch_id, b.snapshot_date::text,
        b.request->>'area', b.row_count, b.capture_status,
        b.manifest->>'paginationStatus', p.page_count
        FROM bronze.distributed_capture_categories q
        LEFT JOIN LATERAL (
            SELECT batch_id, snapshot_date, request, row_count, capture_status, manifest
            FROM bronze.capture_batches b WHERE b.source_jobcat = q.source_jobcat
            ORDER BY b.snapshot_date DESC, b.snapshot_datetime DESC, b.batch_id DESC
            LIMIT 1
        ) b ON TRUE
        LEFT JOIN LATERAL (SELECT COUNT(*) AS page_count
            FROM bronze.capture_pages cp WHERE cp.batch_id = b.batch_id) p ON TRUE
        WHERE {where} ORDER BY q.source_jobcat LIMIT %s OFFSET %s""",
        [*values, PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()
    categories = [{"code": row[0], "name": row[1], "state": row[2],
                   "attempts": row[3], "updatedAt": row[4], "batchId": row[5],
                   "batchDate": row[6], "area": row[7], "rowCount": row[8],
                   "captureStatus": row[9], "paginationStatus": row[10],
                   "pages": row[11]} for row in rows]
    return {"runId": run[0], "total": total, "page": page,
            "pageSize": PAGE_SIZE, "categories": categories}


def fetch_jobs(conn, params):
    code = params.get("jobcat", [""])[0]
    if not code.isdigit() or len(code) > 20:
        raise ValueError("jobcat must be an official numeric category code")
    search = params.get("search", [""])[0].strip()[:120]
    page = page_number(params)
    batch = conn.execute("""SELECT batch_id, snapshot_date::text, request->>'area',
        row_count, capture_status, manifest->>'paginationStatus'
        FROM bronze.capture_batches WHERE source_jobcat = %s
        ORDER BY snapshot_date DESC, snapshot_datetime DESC, batch_id DESC LIMIT 1""",
        (code,)).fetchone()
    if not batch:
        return {"jobcat": code, "batch": None, "total": 0, "page": page,
                "pageSize": JOB_PAGE_SIZE, "jobs": []}
    pattern = f"%{search}%"
    match_sql = """(%s = '' OR COALESCE(job_no, '') ILIKE %s
        OR COALESCE(payload->>'jobName', '') ILIKE %s
        OR COALESCE(payload->>'custName', '') ILIKE %s)"""
    match_args = (search, pattern, pattern, pattern)
    total = conn.execute(f"""SELECT COUNT(*) FROM bronze.raw_job_rows
        WHERE batch_id = %s AND {match_sql}""", (batch[0], *match_args)).fetchone()[0]
    rows = conn.execute(f"""SELECT source_page, row_index, job_no,
        payload->>'jobName', payload->>'custName', payload->>'jobAddrNoDesc',
        payload->>'salaryLow', payload->>'salaryHigh', payload,
        payload_source_json, payload_quality_flags
        FROM bronze.raw_job_rows
        WHERE batch_id = %s AND {match_sql}
        ORDER BY source_page, row_index LIMIT %s OFFSET %s""",
        (batch[0], *match_args, JOB_PAGE_SIZE, (page - 1) * JOB_PAGE_SIZE)).fetchall()
    return {
        "jobcat": code,
        "batch": {"batchId": batch[0], "date": batch[1], "area": batch[2],
                  "rowCount": batch[3], "captureStatus": batch[4],
                  "paginationStatus": batch[5]},
        "total": total, "page": page, "pageSize": JOB_PAGE_SIZE,
        "jobs": [{"page": row[0], "row": row[1], "jobNo": row[2],
                  "jobName": row[3], "company": row[4], "area": row[5],
                  "salaryLow": row[6], "salaryHigh": row[7],
                  "payload": row[8], "payloadSourceJson": row[9],
                  "payloadQualityFlags": row[10]} for row in rows],
    }


class ViewerHandler(BaseHTTPRequestHandler):
    server_version = "PBI104ReadOnlyViewer/1.0"

    def _send(self, body, content_type, status=200):
        encoded = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self'; object-src 'none'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, value, status=200):
        self._send(json.dumps(value, ensure_ascii=True, allow_nan=False, default=str),
                   "application/json; charset=utf-8", status)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path in ASSET_TYPES:
            name = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            self._send((ASSETS / name).read_bytes(), ASSET_TYPES[parsed.path])
            return
        if parsed.path not in {"/api/status", "/api/categories", "/api/jobs"}:
            self._json({"error": "not found"}, 404)
            return
        try:
            with readonly_connection() as conn:
                params = parse_qs(parsed.query, keep_blank_values=True)
                if parsed.path == "/api/status":
                    result = fetch_status(conn)
                elif parsed.path == "/api/categories":
                    result = fetch_categories(conn, params)
                else:
                    result = fetch_jobs(conn, params)
            self._json(result)
        except ValueError as error:
            self._json({"error": str(error)}, 400)
        except Exception as error:
            print(f"Browser viewer query failed: {type(error).__name__}", flush=True)
            self._json({"error": "資料庫暫時無法讀取"}, 503)

    def do_POST(self):
        self._json({"error": "read-only viewer"}, 405)

    def log_message(self, _format, *_args):
        return


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    with readonly_connection() as conn:
        initial = fetch_status(conn)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ViewerHandler)
    print(f"104 read-only data viewer: http://127.0.0.1:{args.port}/ "
          f"({initial.get('status', 'NO_RUN')})", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
