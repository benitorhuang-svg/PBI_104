-- Migration 025: limit yes123 acquisition reporting to WORK_MODE categories.
-- yes123 status reflects persisted category batches; its runner does not persist a live queue.
-- The matching native code ending in 0000 is the L1 display row; show its 1001_0001-style L2 code.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_acquisition_categories AS
WITH yes123_capture_batches AS (
    SELECT b.batch_id, b.native_search_code, b.snapshot_date,
           b.snapshot_datetime, b.capture_status, b.row_count, b.manifest,
           b.manifest->>'paginationStatus' AS pagination_status,
           CASE WHEN b.manifest->>'reportedTotal' ~ '^[0-9]+$'
                THEN (b.manifest->>'reportedTotal')::bigint END
                AS reported_job_count
    FROM fdw_yes123.capture_batches AS b
    WHERE b.source_platform = 'yes123'
      AND b.code_kind = 'YES123_WORK_MODE'
), latest_capture_date AS (
    SELECT MAX(snapshot_date) AS snapshot_date
    FROM yes123_capture_batches
), latest_batch_by_code AS (
    SELECT DISTINCT ON (native_search_code) *
    FROM yes123_capture_batches
    ORDER BY native_search_code, snapshot_date DESC,
             snapshot_datetime DESC, batch_id DESC
), current_batch_counts AS (
    SELECT b.native_search_code,
           COUNT(*) FILTER (WHERE b.snapshot_date = d.snapshot_date)::integer
               AS batch_count
    FROM yes123_capture_batches AS b
    CROSS JOIN latest_capture_date AS d
    GROUP BY b.native_search_code
), yes123_category_rows AS (
    SELECT c.native_category_code,
           c.native_category_name,
           root.native_category_code AS parent_native_category_code,
           root.native_category_name AS parent_native_category_name,
           d.snapshot_date AS latest_snapshot_date,
           b.batch_id,
           b.snapshot_date AS batch_snapshot_date,
           b.snapshot_datetime,
           b.capture_status,
           b.row_count,
           b.manifest,
           b.pagination_status,
           b.reported_job_count,
           COALESCE(cc.batch_count, 0) AS current_batch_count,
           CASE
               WHEN b.batch_id IS NULL THEN 'NOT_CAPTURED'
               WHEN b.snapshot_date < d.snapshot_date THEN 'STALE'
               WHEN b.capture_status = 'COMPLETE'
                    AND b.pagination_status = 'PASS' THEN 'DONE'
               ELSE 'WARNING'
           END AS category_state
    FROM fdw_yes123.category_crosswalk AS c
    CROSS JOIN latest_capture_date AS d
    LEFT JOIN latest_batch_by_code AS b
      ON b.native_search_code = c.native_category_code
    LEFT JOIN current_batch_counts AS cc
      ON cc.native_search_code = c.native_category_code
    -- All current Work Mode codes have a matching same-prefix 0000 display row.
    LEFT JOIN fdw_yes123.category_crosswalk AS root
      ON root.source_platform = c.source_platform
     AND root.native_category_code =
         regexp_replace(c.native_category_code, '_[^_]+$', '_0000')
    WHERE c.source_platform = 'yes123'
      AND LEFT(c.native_category_code, 2) = '2_'
), yes123_progress AS (
    SELECT COUNT(*)::integer AS selected_categories,
           COUNT(*) FILTER (WHERE category_state = 'DONE')::integer
               AS completed_categories,
           COUNT(*) FILTER (
               WHERE batch_snapshot_date = latest_snapshot_date
           )::integer AS recorded_categories,
           MIN(snapshot_datetime) FILTER (
               WHERE batch_snapshot_date = latest_snapshot_date
           ) AS run_started_at,
           MAX(snapshot_datetime) FILTER (
               WHERE batch_snapshot_date = latest_snapshot_date
           ) AS run_updated_at
    FROM yes123_category_rows
)
SELECT ac.*,
       CASE WHEN ac."batchId" IS NULL THEN 0 ELSE 1 END::integer
           AS "batchCount",
       '104'::text AS "sourcePlatform"
FROM gold.pbi_acquisition_categories_104 AS ac
UNION ALL
SELECT NULL::text AS "runId",
       CASE
           WHEN p.completed_categories = p.selected_categories
                THEN 'COMPLETE'
           WHEN p.recorded_categories > 0 THEN 'PARTIAL'
           ELSE 'NOT_STARTED'
       END::text AS "runStatus",
       r.latest_snapshot_date AS "snapshotDate",
       p.selected_categories AS "selectedCategories",
       CASE
           WHEN r.native_category_code ~ '^2_[0-9]{4}_[0-9]{4}_0000$'
               THEN 0
           WHEN r.parent_native_category_code IS NOT NULL THEN 2
           ELSE NULL
       END::integer AS "categoryDepth",
       NULL::text AS "areaFilter",
       NULL::integer AS "pageSize",
       NULL::integer AS "workerCount",
       p.run_started_at AS "runStartedAt",
       p.run_updated_at AS "runUpdatedAt",
       NULL::double precision AS "minimumRequestIntervalSeconds",
       NULL::double precision AS "requestIntervalSeconds",
       NULL::integer AS "gateBlocked",
       CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Taipei' AS "sourceReadAt",
       r.native_category_code AS "categoryCode",
       r.native_category_name AS "categoryName",
       r.category_state AS "categoryState",
       NULL::integer AS "attempts",
       r.snapshot_datetime AS "categoryUpdatedAt",
       CASE r.category_state
           WHEN 'DONE' THEN 'CAPTURED'
           WHEN 'NOT_CAPTURED' THEN 'NOT_CAPTURED'
           WHEN 'STALE' THEN 'STALE'
           ELSE 'WARNING'
       END::text AS "resultStatus",
       r.batch_id AS "batchId",
       CASE
           WHEN r.batch_id IS NULL THEN 'NOT_CAPTURED'
           WHEN r.batch_snapshot_date < r.latest_snapshot_date THEN 'STALE'
           ELSE r.capture_status
       END::text AS "captureStatus",
       CASE
           WHEN r.batch_id IS NULL THEN 'NOT_CAPTURED'
           WHEN r.batch_snapshot_date < r.latest_snapshot_date THEN 'STALE'
           ELSE COALESCE(r.pagination_status, 'UNKNOWN')
       END::text AS "paginationStatus",
       CASE WHEN r.batch_snapshot_date = r.latest_snapshot_date
            THEN COALESCE(r.row_count, 0)::bigint ELSE 0::bigint END
           AS "jobCount",
       CASE WHEN r.batch_snapshot_date = r.latest_snapshot_date
                  AND jsonb_typeof(r.manifest->'pages') = 'array'
            THEN jsonb_array_length(r.manifest->'pages')::bigint
            ELSE 0::bigint END AS "pageCount",
       CASE WHEN r.category_state = 'DONE' THEN 0 ELSE 1 END::integer
           AS "warningFlag",
       COALESCE(r.parent_native_category_name, r.native_category_name)
           || ' (' || COALESCE(r.parent_native_category_code,
                               r.native_category_code) || ')'
           AS "parentCategoryLabel",
       CASE
           WHEN COALESCE(r.parent_native_category_code,
                         r.native_category_code)
                ~ '^2_[0-9]{4}_[0-9]{4}_[0-9]{4}$'
           THEN split_part(COALESCE(r.parent_native_category_code,
                                    r.native_category_code), '_', 2)
                || '_'
                || split_part(COALESCE(r.parent_native_category_code,
                                       r.native_category_code), '_', 3)
           ELSE 'yes123:' || COALESCE(r.parent_native_category_code,
                                      r.native_category_code)
       END AS "parentCategoryCode",
       COALESCE(r.parent_native_category_name, r.native_category_name)
           AS "parentCategoryName",
       CASE WHEN r.batch_snapshot_date = r.latest_snapshot_date
            THEN r.reported_job_count END AS "apiReportedJobCountMin",
       CASE WHEN r.batch_snapshot_date = r.latest_snapshot_date
            THEN r.reported_job_count END AS "apiReportedJobCountMax",
       NULL::bigint AS "apiReportedPageCountMin",
       NULL::bigint AS "apiReportedPageCountMax",
       CASE WHEN r.batch_snapshot_date = r.latest_snapshot_date
            THEN 1 ELSE 0 END::integer AS "queueTerminalFlag",
       CASE WHEN r.category_state = 'DONE' THEN 1 ELSE 0 END::integer
           AS "captureCompleteFlag",
       NULL::integer AS "silverEligibleFlag",
       NULL::integer AS "silverBlockedFlag",
       CASE r.category_state
           WHEN 'NOT_CAPTURED' THEN 'NO_CAPTURE_BATCH'
           WHEN 'STALE' THEN 'NO_BATCH_ON_LATEST_CAPTURE_DATE'
           WHEN 'WARNING' THEN 'CAPTURE_OR_PAGINATION_WARNING'
           ELSE NULL
       END::text AS "warningReason",
       r.current_batch_count AS "batchCount",
       'yes123'::text AS "sourcePlatform"
FROM yes123_category_rows AS r
CROSS JOIN yes123_progress AS p;

INSERT INTO bronze.schema_migrations(version) VALUES (25)
ON CONFLICT (version) DO NOTHING;

COMMIT;
