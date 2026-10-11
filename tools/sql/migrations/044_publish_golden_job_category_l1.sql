-- Migration 044: publish a cross-platform Golden L1 bridge.
--
-- The 104 catalogue remains the canonical taxonomy baseline.  A source
-- category is assigned to that taxonomy only when the source crosswalk says
-- CONFIRMED.  Unmapped yes123 categories remain visible as one explicit
-- BLOCKED bucket so the report does not silently discard those jobs.
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

    SELECT f.job_no AS "jobNo",
           f.source_platform AS "sourcePlatform",
           f.source_jobcat AS "nativeCategoryCode",
           c.native_category_name AS "nativeCategoryName",
           c.canonical_job_cat_code AS "canonicalJobCatCode",
           COALESCE(c.mapping_status, 'BLOCKED') AS "mappingStatus",
           COALESCE(c.match_confidence, 0.00)::numeric AS "matchConfidence"
    FROM gold.pbi_fact_job_scope_v21 AS f
    LEFT JOIN fdw_yes123.category_crosswalk AS c
      ON c.source_platform = 'yes123'
     AND c.native_category_code = f.source_jobcat
    WHERE f.source_platform = 'yes123'
      AND f.source_jobcat IS NOT NULL
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

ALTER VIEW gold.pbi_dim_job_category_v21
    RENAME COLUMN "platformL1Code" TO "goldenL1Code";
ALTER VIEW gold.pbi_dim_job_category_v21
    RENAME COLUMN "platformL1Name" TO "goldenL1Name";

CREATE OR REPLACE VIEW gold.pbi_dim_job_category_v21 AS
WITH category_keys AS (
    SELECT DISTINCT "jobCatCode"
    FROM gold.pbi_bridge_job_category_v21
)
SELECT k."jobCatCode",
       CASE
           WHEN k."jobCatCode" = -1 THEN '未映射來源職類'
           ELSE d.job_cat_description
       END AS "jobCatDescription",
       COALESCE(l1.job_cat_code, -1::bigint) AS "goldenL1Code",
       COALESCE(l1.job_cat_description, '待對照／BLOCKED') AS "goldenL1Name"
FROM category_keys AS k
LEFT JOIN silver.category_dimension AS d
  ON d.job_cat_code = k."jobCatCode"
LEFT JOIN silver.category_dimension AS l1
  ON l1.job_cat_code::text = d.path_codes ->> 0;

INSERT INTO bronze.schema_migrations(version) VALUES (44)
ON CONFLICT (version) DO NOTHING;

COMMIT;
