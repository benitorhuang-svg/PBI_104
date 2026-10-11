-- Migration 043: expose the verified 104 catalogue root as a compact slicer field.
-- Rows without a catalogue path remain explicitly BLOCKED instead of being
-- assigned to an inferred platform category.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_dim_job_category_v21 AS
SELECT DISTINCT b."jobCatCode",
       b."jobCatDescription",
       l1.job_cat_code AS "platformL1Code",
       COALESCE(l1.job_cat_description, 'BLOCKED') AS "platformL1Name"
FROM gold.pbi_bridge_job_category_v21 AS b
LEFT JOIN silver.category_dimension AS child
  ON child.job_cat_code = b."jobCatCode"
LEFT JOIN silver.category_dimension AS l1
  ON l1.job_cat_code::text = child.path_codes ->> 0;

INSERT INTO bronze.schema_migrations(version) VALUES (43)
ON CONFLICT (version) DO NOTHING;

COMMIT;
