-- Migration 046: keep the Golden L1 dimension independent of the large bridge.
-- The explicit unresolved member is retained even when a future source has no
-- pending mappings; it is a stable quality bucket for the report contract.
BEGIN;
SET LOCAL lock_timeout = '5s';

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
)
SELECT "jobCatCode", "jobCatDescription",
       COALESCE("goldenL1Code", -1::bigint) AS "goldenL1Code",
       COALESCE("goldenL1Name", '待對照／BLOCKED') AS "goldenL1Name"
FROM category_rows
UNION ALL
SELECT * FROM unresolved_row;

INSERT INTO bronze.schema_migrations(version) VALUES (46)
ON CONFLICT (version) DO NOTHING;

COMMIT;
