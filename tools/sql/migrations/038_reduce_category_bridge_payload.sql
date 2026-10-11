-- Migration 038: keep the active category bridge at relationship-key grain.
-- The category description remains available from pbi_dim_job_category_v21;
-- the PBIP bridge does not consume that redundant string column.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_keys_v21 AS
SELECT DISTINCT s.job_no AS "jobNo",
       s.job_cat_code AS "jobCatCode"
FROM silver.job_category_snapshots AS s
JOIN gold.pbi_fact_job_scope_v21 AS f
  USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.category_dimension AS d USING (job_cat_code)
WHERE f.source_platform = '104'
UNION ALL
SELECT DISTINCT s.job_no AS "jobNo",
       s.job_cat_code AS "jobCatCode"
FROM fdw_yes123.job_category_snapshots AS s
JOIN gold.pbi_fact_job_scope_v21 AS f
  USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.category_dimension AS d USING (job_cat_code)
WHERE f.source_platform = 'yes123';

INSERT INTO bronze.schema_migrations(version) VALUES (38)
ON CONFLICT (version) DO NOTHING;

COMMIT;
