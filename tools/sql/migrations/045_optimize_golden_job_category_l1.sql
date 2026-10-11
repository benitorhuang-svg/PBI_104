-- Migration 045: keep the Golden L1 bridge local and avoid row-wise FDW lookups.
-- The reviewed crosswalk is already present in reporting Silver; using it here
-- preserves the same mapping status while keeping Power BI refresh bounded.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_golden_v22 AS
WITH source_assignments AS (
    SELECT f.job_no AS "jobNo",
           f.source_platform AS "sourcePlatform",
           s.job_cat_code::text AS "nativeCategoryCode",
           d.job_cat_description AS "nativeCategoryName",
           s.job_cat_code AS "canonicalJobCatCode",
           'CONFIRMED'::text AS "mappingStatus",
           1.00::numeric AS "matchConfidence"
    FROM silver.job_category_snapshots AS s
    JOIN gold.pbi_fact_job_scope_v21 AS f
      USING (series_key, snapshot_date, batch_id, job_no)
    JOIN silver.category_dimension AS d
      USING (job_cat_code)
    WHERE f.source_platform = '104'

    UNION ALL

    SELECT f."jobNo",
           f."sourcePlatform",
           j.source_jobcat AS "nativeCategoryCode",
           c.native_category_name AS "nativeCategoryName",
           c.canonical_job_cat_code AS "canonicalJobCatCode",
           COALESCE(c.mapping_status, 'BLOCKED') AS "mappingStatus",
           COALESCE(c.match_confidence, 0.00)::numeric AS "matchConfidence"
    FROM gold.pbi_fact_jobs_v22 AS f
    JOIN fdw_yes123.job_current AS j
      ON j.job_no = f."jobNo"
     AND j.source_platform = 'yes123'
    LEFT JOIN silver.category_crosswalk AS c
      ON c.source_platform = 'yes123'
     AND c.native_category_code = j.source_jobcat
    WHERE f."sourcePlatform" = 'yes123'
      AND j.source_jobcat IS NOT NULL
),
resolved_assignments AS (
    SELECT a.*,
           d.job_cat_description AS "canonicalJobCatName",
           l1.job_cat_code AS "goldenL1Code",
           l1.job_cat_description AS "goldenL1Name"
    FROM source_assignments AS a
    LEFT JOIN silver.category_dimension AS d
      ON d.job_cat_code = a."canonicalJobCatCode"
    LEFT JOIN silver.category_dimension AS l1
      ON l1.job_cat_code::text = d.path_codes ->> 0
)
SELECT DISTINCT "jobNo",
       "sourcePlatform",
       "nativeCategoryCode",
       "nativeCategoryName",
       "canonicalJobCatCode",
       "canonicalJobCatName",
       "mappingStatus",
       "matchConfidence",
       "goldenL1Code",
       "goldenL1Name"
FROM resolved_assignments;

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_v21 AS
SELECT DISTINCT g."jobNo",
       COALESCE(g."canonicalJobCatCode", -1::bigint) AS "jobCatCode",
       COALESCE(g."canonicalJobCatName", '未映射來源職類') AS "jobCatDescription"
FROM gold.pbi_bridge_job_category_golden_v22 AS g;

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_keys_v21 AS
SELECT DISTINCT "jobNo", "jobCatCode"
FROM gold.pbi_bridge_job_category_v21;

CREATE OR REPLACE VIEW gold.pbi_dim_job_category_v21 AS
WITH category_rows AS (
    SELECT d.job_cat_code AS "jobCatCode",
           d.job_cat_description AS "jobCatDescription",
           l1.job_cat_code AS "goldenL1Code",
           l1.job_cat_description AS "goldenL1Name"
    FROM silver.category_dimension AS d
    LEFT JOIN silver.category_dimension AS l1
      ON l1.job_cat_code::text = d.path_codes ->> 0
), unresolved_row AS (
    SELECT -1::bigint AS "jobCatCode",
           '未映射來源職類'::text AS "jobCatDescription",
           -1::bigint AS "goldenL1Code",
           '待對照／BLOCKED'::text AS "goldenL1Name"
    WHERE EXISTS (
        SELECT 1
        FROM gold.pbi_bridge_job_category_golden_v22
        WHERE "canonicalJobCatCode" IS NULL
    )
)
SELECT "jobCatCode", "jobCatDescription",
       COALESCE("goldenL1Code", -1::bigint) AS "goldenL1Code",
       COALESCE("goldenL1Name", '待對照／BLOCKED') AS "goldenL1Name"
FROM category_rows
UNION ALL
SELECT * FROM unresolved_row;

INSERT INTO bronze.schema_migrations(version) VALUES (45)
ON CONFLICT (version) DO NOTHING;

COMMIT;
