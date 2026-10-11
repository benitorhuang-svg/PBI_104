-- Migration 039: keep the active skill bridge at relationship-key grain.
-- The skill description is an exact match to silver.skill_dimension for every
-- current bridge row; the PBIP bridge no longer imports that redundant text.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_bridge_job_skill_keys_v21 AS
SELECT DISTINCT s.job_no AS "jobNo",
       s.skill_code AS "skillCode"
FROM silver.job_skill_snapshots AS s
JOIN gold.pbi_fact_job_scope_v21 AS f
  USING (series_key, snapshot_date, batch_id, job_no)
WHERE f.source_platform = '104';

INSERT INTO bronze.schema_migrations(version) VALUES (39)
ON CONFLICT (version) DO NOTHING;

COMMIT;
