-- Migration 023: read the yes123 Gold job scope as one remote projection.
-- Avoids per-row FDW lookups across job, company, and area tables.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE FOREIGN TABLE IF NOT EXISTS fdw_yes123.pbi_fact_job_scope (
    series_key text,
    snapshot_date date,
    batch_id text,
    job_no text,
    cust_no text,
    area_key text,
    salary_low numeric,
    salary_high numeric,
    appear_date date,
    snapshot_datetime timestamp without time zone,
    source_keyword text,
    source_area text,
    source_jobcat text,
    job_name text,
    desc_snippet text,
    job_link text,
    company_name text,
    co_industry integer,
    co_industry_desc text,
    job_addr_no bigint,
    job_addr_no_desc text,
    job_address text,
    source_platform text,
    native_job_id text,
    source_job_key text
) SERVER srv_jobwant_yes123
OPTIONS (schema_name 'gold', table_name 'pbi_fact_job_scope');

CREATE OR REPLACE VIEW gold.pbi_fact_job_scope_v21 AS
WITH latest_104_observations AS (
    SELECT DISTINCT ON (s.job_no)
           s.series_key, s.snapshot_date, s.batch_id, s.job_no, s.cust_no,
           s.area_key, s.salary_low, s.salary_high, s.appear_date,
           s.snapshot_datetime, s.source_keyword, s.source_area, s.source_jobcat,
           '104'::text AS source_platform,
           COALESCE(s.native_job_id, s.job_no) AS native_job_id,
           COALESCE(s.source_job_key, '104:' || s.job_no) AS source_job_key
    FROM gold.latest_job_snapshots AS s
    WHERE s.source_jobcat IS NOT NULL
      AND COALESCE(s.source_keyword, '') = ''
      AND COALESCE(s.source_platform, '104') = '104'
    ORDER BY s.job_no, s.snapshot_datetime DESC, s.series_key, s.batch_id DESC
), obs_104 AS (
    SELECT s.series_key, s.snapshot_date, s.batch_id, s.job_no, s.cust_no,
           s.area_key, s.salary_low, s.salary_high, s.appear_date,
           s.snapshot_datetime AT TIME ZONE 'Asia/Taipei' AS snapshot_datetime,
           s.source_keyword, s.source_area, s.source_jobcat,
           j.job_name, j.desc_snippet, j.job_link,
           c.company_name, c.co_industry, c.co_industry_desc,
           a.job_addr_no, a.job_addr_no_desc, a.job_address,
           s.source_platform, s.native_job_id, s.source_job_key
    FROM latest_104_observations AS s
    JOIN silver.job_current AS j ON j.job_no = s.job_no
    LEFT JOIN silver.company_dimension AS c ON c.cust_no = s.cust_no
    LEFT JOIN silver.area_dimension AS a ON a.area_key = s.area_key
), obs_yes123 AS (
    SELECT s.series_key, s.snapshot_date, s.batch_id, s.job_no, s.cust_no,
           s.area_key, NULL::numeric AS salary_low, NULL::numeric AS salary_high,
           s.appear_date, s.snapshot_datetime,
           s.source_keyword, s.source_area, s.source_jobcat,
           s.job_name, s.desc_snippet, s.job_link,
           s.company_name, s.co_industry, s.co_industry_desc,
           s.job_addr_no, s.job_addr_no_desc, s.job_address,
           s.source_platform, s.native_job_id, s.source_job_key
    FROM fdw_yes123.pbi_fact_job_scope AS s
)
SELECT * FROM obs_104
UNION ALL
SELECT * FROM obs_yes123;

INSERT INTO bronze.schema_migrations(version) VALUES (23)
ON CONFLICT (version) DO NOTHING;

COMMIT;
