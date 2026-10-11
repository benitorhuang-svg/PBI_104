-- Migration 048: Optimize category bridge join performance and escape governance.
-- Resolves the cartesian product / nested loop join bottleneck in
-- gold.pbi_bridge_job_category_golden_v22 by joining path_codes cast to bigint,
-- and re-validates yes123 category crosswalk mappings.
BEGIN;
SET LOCAL lock_timeout = '5s';

-- 1. Re-create gold.pbi_bridge_job_category_golden_v22 with indexed bigint join
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
    LEFT JOIN silver.category_crosswalk AS c
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
      ON l1.job_cat_code = NULLIF(d.path_codes ->> 0, '')::bigint
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

-- 2. Ensure v21 category bridge views preserve existing contracts
CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_v21 AS
SELECT DISTINCT g."jobNo",
       COALESCE(g."canonicalJobCatCode", -1::bigint) AS "jobCatCode",
       COALESCE(g."canonicalJobCatName", '未映射來源職類') AS "jobCatDescription"
FROM gold.pbi_bridge_job_category_golden_v22 AS g;

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_keys_v21 AS
SELECT DISTINCT "jobNo", "jobCatCode"
FROM gold.pbi_bridge_job_category_v21;

-- 3. Record migration version
INSERT INTO bronze.schema_migrations(version) VALUES (48)
ON CONFLICT (version) DO NOTHING;

COMMIT;
