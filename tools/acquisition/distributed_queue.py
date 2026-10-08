"""PostgreSQL-backed category work queue shared by Compose worker replicas."""

from psycopg.types.json import Jsonb


def register_run(conn, run, categories):
    """Create a deterministic daily work set and reopen failed work on resume."""
    with conn.transaction():
        inserted = conn.execute("""INSERT INTO bronze.distributed_capture_runs
            (run_id, run_key, snapshot_date, catalog_sha256, category_depth,
             area_filter, pagesize, minimum_interval_seconds, worker_count,
             selected_categories)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_key) DO NOTHING RETURNING run_id""",
            (run["runId"], run["runKey"], run["snapshotDate"], run["catalogSha256"],
             run["depth"], run["area"], run["pagesize"], run["delay"],
             run["workerCount"], len(categories)))
        saved = conn.execute("""SELECT run_id, status, selected_categories
            FROM bronze.distributed_capture_runs WHERE run_key = %s FOR UPDATE""",
            (run["runKey"],)).fetchone()
        if not saved:
            raise RuntimeError("Could not create or find the distributed capture run")
        run_id, prior_status, selected = saved
        if selected != len(categories):
            raise ValueError("Existing distributed run has a different category count")
        with conn.cursor() as cursor:
            cursor.executemany("""INSERT INTO bronze.distributed_capture_categories
                (run_id, source_jobcat, category_name) VALUES (%s, %s, %s)
                ON CONFLICT (run_id, source_jobcat) DO NOTHING""",
                [(run_id, str(item["code"]), item["name"]) for item in categories])
        if prior_status in ("PARTIAL", "BLOCKED"):
            conn.execute("""UPDATE bronze.distributed_capture_categories
                SET state = 'PENDING', lease_owner = NULL, lease_expires_at = NULL,
                    last_error = NULL, result = NULL, batch_id = NULL,
                    available_at = clock_timestamp(),
                    updated_at = clock_timestamp()
                WHERE run_id = %s AND state IN ('FAIL', 'DEFERRED')""", (run_id,))
            conn.execute("""UPDATE bronze.distributed_capture_runs
                SET status = 'QUEUED', completed_at = NULL, updated_at = clock_timestamp()
                WHERE run_id = %s""", (run_id,))
        if inserted or prior_status in ("PARTIAL", "BLOCKED"):
            conn.execute("""UPDATE bronze.capture_request_state
                SET blocked_reason = NULL, blocked_until = clock_timestamp(),
                    success_count = 0,
                    interval_seconds = GREATEST(interval_seconds, minimum_interval_seconds),
                    updated_at = clock_timestamp()
                WHERE channel = '104_jobs'""")
        return run_id


def claim_next(conn, worker_id, lease_seconds=900):
    """Atomically lease one category; expired claims can be recovered."""
    with conn.transaction():
        row = conn.execute("""WITH candidate AS (
                SELECT q.run_id, q.source_jobcat,
                     r.snapshot_date::text AS snapshot_date,
                     r.catalog_sha256,
                     r.category_depth, r.area_filter, r.pagesize,
                     r.minimum_interval_seconds, r.worker_count
                FROM bronze.distributed_capture_categories AS q
                JOIN bronze.distributed_capture_runs AS r USING (run_id)
                WHERE r.status IN ('QUEUED', 'RUNNING')
                  AND NOT EXISTS (SELECT 1 FROM bronze.capture_request_state
                    WHERE channel = '104_jobs' AND blocked_reason IS NOT NULL)
                  AND ((q.state = 'PENDING' AND q.available_at <= clock_timestamp())
                    OR (q.state = 'LEASED' AND q.lease_expires_at <= clock_timestamp()))
                ORDER BY r.created_at, q.attempts, q.source_jobcat
                FOR UPDATE OF q SKIP LOCKED
                LIMIT 1
            )
            UPDATE bronze.distributed_capture_categories AS q
            SET state = 'LEASED', lease_owner = %s,
                lease_expires_at = clock_timestamp() + (%s * interval '1 second'),
                attempts = q.attempts + 1, result = NULL, last_error = NULL,
                updated_at = clock_timestamp()
            FROM candidate AS c
            WHERE q.run_id = c.run_id AND q.source_jobcat = c.source_jobcat
            RETURNING q.run_id, q.source_jobcat, q.category_name, q.attempts,
                c.snapshot_date, c.catalog_sha256, c.category_depth, c.area_filter,
                c.pagesize, c.minimum_interval_seconds, c.worker_count""",
            (worker_id, lease_seconds)).fetchone()
        if row:
            conn.execute("""UPDATE bronze.distributed_capture_runs
                SET status = 'RUNNING', started_at = COALESCE(started_at, clock_timestamp()),
                    updated_at = clock_timestamp() WHERE run_id = %s""", (row[0],))
        return row


def has_unfinished_work(conn):
    with conn.transaction():
        return conn.execute("""SELECT EXISTS (
            SELECT 1 FROM bronze.distributed_capture_categories AS q
            JOIN bronze.distributed_capture_runs AS r USING (run_id)
            WHERE r.status IN ('QUEUED', 'RUNNING')
              AND q.state IN ('PENDING', 'LEASED'))""").fetchone()[0]


def heartbeat(conn, run_id, code, worker_id, lease_seconds=900):
    result = conn.execute("""UPDATE bronze.distributed_capture_categories
        SET lease_expires_at = clock_timestamp() + (%s * interval '1 second'),
            updated_at = clock_timestamp()
        WHERE run_id = %s AND source_jobcat = %s AND state = 'LEASED'
          AND lease_owner = %s""", (lease_seconds, run_id, code, worker_id))
    return result.rowcount == 1


def _refresh_run(conn, run_id):
    counts = conn.execute("""SELECT
        COUNT(*) FILTER (WHERE state IN ('PENDING', 'LEASED')) AS active,
        COUNT(*) FILTER (WHERE state = 'FAIL') AS failed,
        COUNT(*) FILTER (WHERE state = 'DEFERRED') AS deferred,
        COUNT(*) FILTER (WHERE bronze.acquisition_category_warning(
            q.result, b.capture_status, b.manifest->>'paginationStatus')) AS warnings
        FROM bronze.distributed_capture_categories AS q
        LEFT JOIN bronze.capture_batches AS b ON b.batch_id = q.batch_id
        WHERE q.run_id = %s""",
        (run_id,)).fetchone()
    active, failed, deferred, warnings = counts
    if deferred:
        status, completed = "BLOCKED", not bool(active)
    elif active:
        status, completed = "RUNNING", False
    elif failed:
        status, completed = "PARTIAL", True
    elif warnings:
        status, completed = "COMPLETE_WITH_WARNINGS", True
    else:
        status, completed = "COMPLETE", True
    conn.execute("""UPDATE bronze.distributed_capture_runs
        SET status = %s, completed_at = CASE WHEN %s THEN clock_timestamp() ELSE NULL END,
            updated_at = clock_timestamp() WHERE run_id = %s""",
        (status, completed, run_id))
    return status


def complete_category(conn, run_id, code, worker_id, result, batch_id=None):
    with conn.transaction():
        updated = conn.execute("""UPDATE bronze.distributed_capture_categories
            SET state = 'DONE', result = %s, batch_id = %s, last_error = NULL,
                lease_owner = NULL, lease_expires_at = NULL,
                updated_at = clock_timestamp()
            WHERE run_id = %s AND source_jobcat = %s AND state = 'LEASED'
              AND lease_owner = %s""",
            (Jsonb(result), batch_id, run_id, code, worker_id))
        if updated.rowcount != 1:
            raise RuntimeError(f"Category lease was lost before completion: {code}")
        conn.execute("SELECT run_id FROM bronze.distributed_capture_runs "
                     "WHERE run_id = %s FOR UPDATE", (run_id,))
        return _refresh_run(conn, run_id)


def fail_category(conn, run_id, code, worker_id, result, deferred=False):
    state = "DEFERRED" if deferred else "FAIL"
    with conn.transaction():
        updated = conn.execute("""UPDATE bronze.distributed_capture_categories
            SET state = %s, result = %s, last_error = %s,
                lease_owner = NULL, lease_expires_at = NULL,
                updated_at = clock_timestamp()
            WHERE run_id = %s AND source_jobcat = %s AND state = 'LEASED'
              AND lease_owner = %s""",
            (state, Jsonb(result), result.get("error", "")[:4000],
             run_id, code, worker_id))
        if updated.rowcount != 1:
            return None
        conn.execute("SELECT run_id FROM bronze.distributed_capture_runs "
                     "WHERE run_id = %s FOR UPDATE", (run_id,))
        return _refresh_run(conn, run_id)


def run_progress(conn, run_id=None):
    if run_id:
        run = conn.execute("""SELECT run_id, status, selected_categories
            FROM bronze.distributed_capture_runs WHERE run_id = %s""", (run_id,)).fetchone()
    else:
        run = conn.execute("""SELECT run_id, status, selected_categories
            FROM bronze.distributed_capture_runs ORDER BY created_at DESC LIMIT 1""").fetchone()
    if not run:
        return None
    rows = conn.execute("""SELECT source_jobcat, category_name, state, result
        FROM bronze.distributed_capture_categories WHERE run_id = %s
        ORDER BY source_jobcat""", (run[0],)).fetchall()
    return {"runId": run[0], "status": run[1], "selectedCategories": run[2],
            "categories": rows}
