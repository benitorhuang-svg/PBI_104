"""Publish one race-safe local progress summary for a distributed capture run."""

from datetime import datetime
from zoneinfo import ZoneInfo

from .category_run_storage import save_run


STATUS_NAMES = ("CAPTURED", "CAPTURED_WITH_WARNING", "SKIPPED", "FAIL",
                "DEFERRED", "INSPECTED")


def save_distributed_summary(conn, run_id, output):
    """Serialize summary writers through PostgreSQL and atomically replace JSON."""
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (run_id,))
        run = conn.execute("""SELECT run_id, status, snapshot_date::text,
            catalog_sha256, category_depth, area_filter, pagesize,
            minimum_interval_seconds, worker_count, selected_categories
            FROM bronze.distributed_capture_runs WHERE run_id = %s""",
            (run_id,)).fetchone()
        if not run:
            raise ValueError(f"Unknown distributed run: {run_id}")
        rows = conn.execute("""SELECT source_jobcat, category_name, state, result
            FROM bronze.distributed_capture_categories WHERE run_id = %s
            ORDER BY source_jobcat""", (run_id,)).fetchall()
        queue_counts = dict(conn.execute("""SELECT state, COUNT(*)
            FROM bronze.distributed_capture_categories WHERE run_id = %s
            GROUP BY state""", (run_id,)).fetchall())
        warning_categories, skipped_warning_categories = conn.execute("""SELECT
                COUNT(*) FILTER (WHERE bronze.acquisition_category_warning(
                    q.result, b.capture_status, b.manifest->>'paginationStatus')),
                COUNT(*) FILTER (WHERE q.result->>'status' = 'SKIPPED'
                    AND bronze.acquisition_category_warning(
                        q.result, b.capture_status, b.manifest->>'paginationStatus'))
            FROM bronze.distributed_capture_categories AS q
            LEFT JOIN bronze.capture_batches AS b ON b.batch_id = q.batch_id
            WHERE q.run_id = %s
            """, (run_id,)).fetchone()
        gate = conn.execute("""SELECT minimum_interval_seconds, interval_seconds
            FROM bronze.capture_request_state WHERE channel = '104_jobs'""").fetchone()
        minimum_interval, interval = gate
        depth_count = conn.execute("""SELECT COUNT(*) FROM bronze.job_category_catalog_rows
            WHERE catalog_sha256 = %s AND hierarchy_depth = %s""",
            (run[3], run[4])).fetchone()[0]

        results = []
        for code, name, state, result in rows:
            if result:
                results.append(result)
            elif state == "LEASED":
                results.append({"status": "RUNNING", "code": code, "name": name})
        counts = {name: sum(item.get("status") == name for item in results)
                  for name in STATUS_NAMES}
        terminal = sum(counts.values())
        captured = counts["CAPTURED"] + counts["CAPTURED_WITH_WARNING"]
        successful = counts["CAPTURED"] + counts["CAPTURED_WITH_WARNING"] + counts["SKIPPED"]
        summary = {
            "schemaVersion": 1,
            "mode": "distributed-capture",
            "status": run[1],
            "runId": run[0],
            "generatedAt": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(
                timespec="seconds"),
            "snapshotDate": run[2],
            "catalogSha256": run[3].strip(),
            "officialCategoryCount": depth_count,
            "categoryDepth": run[4],
            "selectedCategories": run[9],
            "area": run[5],
            "pagesize": run[6],
            "storage": "postgresql-bronze",
            "pageWorkersPerCategory": 1,
            "categoryWorkers": run[8],
            "minimumRequestIntervalSeconds": round(minimum_interval, 2),
            "requestIntervalSeconds": round(interval, 2),
            "completedCategories": successful,
            "capturedCategories": captured,
            "terminalCategories": terminal,
            "runningCategories": queue_counts.get("LEASED", 0),
            "pendingCategories": queue_counts.get("PENDING", 0),
            "failedCategories": queue_counts.get("FAIL", 0),
            "deferredCategories": queue_counts.get("DEFERRED", 0),
            "progressPercent": round(100 * successful / run[9], 1) if run[9] else 100.0,
            "categoryStatusCounts": counts,
            "successfulCategories": successful,
            "warningCategories": warning_categories,
            "skippedWarningCategories": skipped_warning_categories,
            "totalJobs": sum(item.get("totalJobs", item.get("rows", 0)) for item in results),
            "retryAttempts": sum(item.get("retryAttempts", 0) for item in results),
            "backoffSeconds": round(sum(item.get("backoffSeconds", 0) for item in results), 2),
            "categories": results,
        }
        save_run(output, run_id, summary)
        return summary
