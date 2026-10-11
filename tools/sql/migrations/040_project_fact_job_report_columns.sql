-- Migration 040: publish only the active report columns for FactJob.
-- The canonical v22 view remains intact for ETL and lineage consumers. These
-- seven unused source/lineage columns are not part of the active PBIP model.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_fact_jobs_report_v22 AS
SELECT "jobNo",
       "custNo",
       "areaKey",
       "jobName",
       "descSnippet",
       "jobAddress",
       "jobAddrNoDesc",
       "salaryLow",
       "salaryHigh",
       "appearDate",
       "jobLink",
       "snapshotDate",
       "snapshotDateTime",
       "sourcePlatform"
FROM gold.pbi_fact_jobs_v22;

INSERT INTO bronze.schema_migrations(version) VALUES (40)
ON CONFLICT (version) DO NOTHING;

COMMIT;
