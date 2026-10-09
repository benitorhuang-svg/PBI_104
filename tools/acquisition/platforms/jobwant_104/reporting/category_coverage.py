"""Read-only per-category coverage report from the current PostgreSQL catalog."""

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from ..persistence.loader import read_db_config


REPORT_SQL = """
WITH catalog AS (
    SELECT catalog_sha256, captured_at
    FROM bronze.job_category_catalogs
    ORDER BY captured_at DESC, catalog_sha256 DESC
    LIMIT 1
), latest_capture AS (
    SELECT DISTINCT ON (source_jobcat)
        source_jobcat, batch_id, snapshot_date, request, row_count, capture_status, manifest
    FROM bronze.capture_batches
    WHERE source_jobcat IS NOT NULL
    ORDER BY source_jobcat, snapshot_date DESC, snapshot_datetime DESC, batch_id DESC
), page_stats AS (
    SELECT batch_id, count(*)::integer AS pages_fetched,
        min((response_metadata #>> '{pagination,lastPage}')::integer) AS api_last_page_min,
        max((response_metadata #>> '{pagination,lastPage}')::integer) AS api_last_page_max,
        min((response_metadata #>> '{pagination,total}')::bigint) AS api_total_min,
        max((response_metadata #>> '{pagination,total}')::bigint) AS api_total_max
    FROM bronze.capture_pages
    GROUP BY batch_id
)
SELECT c.catalog_sha256, c.captured_at::text AS catalog_captured_at,
    r.job_cat_code::text AS code, r.category_name,
    b.batch_id, b.snapshot_date::text AS snapshot_date, b.request->>'area' AS query_area,
    b.row_count,
    b.capture_status, COALESCE(b.manifest->>'paginationStatus', 'PASS') AS pagination_status,
    b.manifest->'paginationDiagnostics' AS pagination_diagnostics,
    p.pages_fetched, p.api_last_page_min, p.api_last_page_max,
    p.api_total_min, p.api_total_max
FROM catalog c
JOIN bronze.job_category_catalog_rows r ON r.catalog_sha256 = c.catalog_sha256
LEFT JOIN latest_capture b ON b.source_jobcat = r.job_cat_code::text
LEFT JOIN page_stats p ON p.batch_id = b.batch_id
WHERE r.is_leaf
ORDER BY r.job_cat_code
"""

FIELDS = (
    "code", "category_name", "status", "batch_id", "snapshot_date", "query_area", "row_count",
    "capture_status", "pagination_status", "pages_fetched", "api_last_page_min",
    "api_last_page_max", "api_total_min", "api_total_max", "page_limit_reached",
)


def category_record(row):
    (_, _, code, name, batch_id, snapshot_date, query_area, row_count,
     capture_status, pagination_status, diagnostics, pages, last_min, last_max,
     total_min, total_max) = row
    status = ("NOT_CAPTURED" if batch_id is None else
              "COMPLETE" if capture_status == "COMPLETE" else "BRONZE_ONLY")
    return {
        "code": code, "category_name": name, "status": status, "batch_id": batch_id,
        "snapshot_date": snapshot_date, "query_area": query_area, "row_count": row_count,
        "capture_status": capture_status, "pagination_status": pagination_status,
        "pages_fetched": pages, "api_last_page_min": last_min,
        "api_last_page_max": last_max, "api_total_min": total_min,
        "api_total_max": total_max,
        "page_limit_reached": (diagnostics or {}).get("pageLimitReached", False),
    }


def fetch_coverage(config):
    import psycopg

    with psycopg.connect(**config) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            migration = conn.execute(
                "SELECT COALESCE(max(version), 0) FROM bronze.schema_migrations"
            ).fetchone()[0]
            rows = conn.execute(REPORT_SQL).fetchall()
    if not rows:
        raise ValueError("No official category catalogue is available in PostgreSQL")
    categories = [category_record(row) for row in rows]
    counts = {name: sum(item["status"] == name for item in categories)
              for name in ("COMPLETE", "BRONZE_ONLY", "NOT_CAPTURED")}
    counts["complete_without_area_filter"] = sum(
        item["status"] == "COMPLETE" and item["query_area"] is None for item in categories)
    return {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "databaseSchemaVersion": migration,
        "catalogSha256": rows[0][0].strip(),
        "catalogCapturedAt": rows[0][1],
        "scope": "latest committed batch per official leaf category",
        "officialLeafCategories": len(categories),
        "summary": counts,
        "categories": categories,
    }


def write_csv(report, stream):
    writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(report["categories"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--format", choices=("json", "csv", "summary"), default="json")
    parser.add_argument("--output", type=Path,
                        help="Optional UTF-8 output file; parent directory must exist")
    args = parser.parse_args()
    report = fetch_coverage(read_db_config(args.env_file))
    if args.output:
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        with args.output.open("w", encoding=encoding, newline="") as stream:
            emit(report, args.format, stream)
    else:
        emit(report, args.format, sys.stdout)
    return 0


def emit(report, output_format, stream):
    if output_format == "csv":
        write_csv(report, stream)
    elif output_format == "summary":
        stream.write(json.dumps({key: value for key, value in report.items()
                                 if key != "categories"}, ensure_ascii=True) + "\n")
    else:
        stream.write(json.dumps(report, ensure_ascii=True, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
