-- Migration 022: align the yes123 salary FDW currency type with its CHAR(3) source.
-- Safe to reapply; only the dependent salary projection is replaced.
BEGIN;
SET LOCAL lock_timeout = '5s';

DROP VIEW IF EXISTS gold.pbi_fact_salary_observations_v21;
ALTER FOREIGN TABLE fdw_yes123.job_salary_observations
    ALTER COLUMN currency_code TYPE character(3);

CREATE VIEW gold.pbi_fact_salary_observations_v21 AS
SELECT s.series_key AS "querySeriesKey", s.snapshot_date AS "snapshotDate",
       s.batch_id AS "batchId", s.job_no AS "jobNo",
       '104'::text AS "sourcePlatform", s.source_kind AS "sourceKind",
       s.observation_index AS "observationIndex", s.raw_value_min AS "rawValueMin",
       s.raw_value_max AS "rawValueMax", s.amount_min AS "amountMin",
       s.amount_max AS "amountMax", btrim(s.currency_code::text) AS "currencyCode",
       s.currency_basis AS "currencyBasis", s.pay_period AS "payPeriod",
       s.range_kind AS "rangeKind", s.compensation_component AS "compensationComponent",
       s.evidence_text AS "evidenceText", s.evidence_start AS "evidenceStart",
       s.evidence_end AS "evidenceEnd", s.parse_status AS "parseStatus",
       s.quality_flags::text AS "qualityFlags", s.confidence AS "confidence",
       s.parser_version AS "parserVersion"
FROM silver.job_salary_observations AS s
UNION ALL
SELECT s.series_key AS "querySeriesKey", s.snapshot_date AS "snapshotDate",
       s.batch_id AS "batchId", s.job_no AS "jobNo",
       'yes123'::text AS "sourcePlatform", s.source_kind AS "sourceKind",
       s.observation_index AS "observationIndex", s.raw_value_min AS "rawValueMin",
       s.raw_value_max AS "rawValueMax", s.amount_min AS "amountMin",
       s.amount_max AS "amountMax", btrim(s.currency_code::text) AS "currencyCode",
       s.currency_basis AS "currencyBasis", s.pay_period AS "payPeriod",
       s.range_kind AS "rangeKind", s.compensation_component AS "compensationComponent",
       s.evidence_text AS "evidenceText", s.evidence_start AS "evidenceStart",
       s.evidence_end AS "evidenceEnd", s.parse_status AS "parseStatus",
       s.quality_flags::text AS "qualityFlags", s.confidence AS "confidence",
       s.parser_version AS "parserVersion"
FROM fdw_yes123.job_salary_observations AS s;

INSERT INTO bronze.schema_migrations(version) VALUES (22)
ON CONFLICT (version) DO NOTHING;

COMMIT;
