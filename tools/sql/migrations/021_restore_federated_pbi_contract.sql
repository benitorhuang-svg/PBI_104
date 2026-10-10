-- Migration 021: Restore the full Power BI Gold contract over jobwant_104 + yes123 FDW.
-- Requires migration 020's existing srv_jobwant_yes123 server and fdw_yes123 schema.
-- This migration changes Gold views and adds narrow foreign projections only; it
-- does not rewrite Bronze/Silver data, replace the FDW server, or store credentials.
BEGIN;

DO $$
BEGIN
    IF to_regclass('fdw_yes123.job_snapshots') IS NULL
       OR to_regclass('fdw_yes123.job_current') IS NULL
       OR to_regclass('fdw_yes123.company_dimension') IS NULL
       OR to_regclass('fdw_yes123.area_dimension') IS NULL
       OR to_regclass('fdw_yes123.job_category_snapshots') IS NULL THEN
        RAISE EXCEPTION 'Migration 021 requires the existing yes123 foreign tables from migration 020';
    END IF;
END $$;

CREATE FOREIGN TABLE IF NOT EXISTS fdw_yes123.job_salary_observations (
    series_key text,
    snapshot_date date,
    batch_id text,
    job_no text,
    source_kind text,
    observation_index integer,
    raw_value_min text,
    raw_value_max text,
    amount_min numeric,
    amount_max numeric,
    currency_code character(3),
    currency_basis text,
    pay_period text,
    range_kind text,
    compensation_component text,
    evidence_text text,
    evidence_start integer,
    evidence_end integer,
    parse_status text,
    quality_flags jsonb,
    confidence numeric,
    parser_version text
) SERVER srv_jobwant_yes123
OPTIONS (schema_name 'silver', table_name 'job_salary_observations');

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

-- The yes123 source contract declares currency_code as CHAR(3), matching 104.
-- ALTER also repairs installations where an earlier draft created this FDW
-- column as the PostgreSQL default CHAR(1).
ALTER FOREIGN TABLE fdw_yes123.job_salary_observations
    ALTER COLUMN currency_code TYPE character(3);

CREATE VIEW gold.pbi_fact_job_scope_v21 AS
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
           s.appear_date,
           s.snapshot_datetime AT TIME ZONE 'Asia/Taipei' AS snapshot_datetime,
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

CREATE VIEW gold.pbi_fact_jobs_v21 AS
SELECT job_no AS "jobNo", cust_no AS "custNo",
       encode(convert_to(area_key, 'UTF8'), 'hex') AS "areaKey",
       job_name AS "jobName", desc_snippet AS "descSnippet",
       job_address AS "jobAddress", job_addr_no_desc AS "jobAddrNoDesc",
       salary_low AS "salaryLow", salary_high AS "salaryHigh",
       appear_date AS "appearDate", job_link AS "jobLink",
       snapshot_date AS "snapshotDate", snapshot_datetime AS "snapshotDateTime",
       source_keyword AS "sourceKeyword", source_area AS "sourceArea",
       source_platform AS "sourcePlatform", native_job_id AS "nativeJobId",
       source_job_key AS "sourceJobKey"
FROM gold.pbi_fact_job_scope_v21;

CREATE VIEW gold.pbi_fact_job_snapshots_v21 AS
SELECT series_key AS "querySeriesKey", snapshot_date AS "snapshotDate",
       snapshot_datetime AS "snapshotDateTime", job_no AS "jobNo",
       cust_no AS "custNo", salary_low AS "salaryLow", salary_high AS "salaryHigh",
       appear_date AS "appearDate", source_keyword AS "sourceKeyword",
       source_area AS "sourceArea", '104'::text AS "sourcePlatform"
FROM gold.pbi_job_snapshots
UNION ALL
SELECT series_key AS "querySeriesKey", snapshot_date AS "snapshotDate",
       snapshot_datetime AT TIME ZONE 'Asia/Taipei' AS "snapshotDateTime",
       job_no AS "jobNo", cust_no AS "custNo",
       NULL::numeric AS "salaryLow", NULL::numeric AS "salaryHigh",
       appear_date AS "appearDate", source_keyword AS "sourceKeyword",
       source_area AS "sourceArea", 'yes123'::text AS "sourcePlatform"
FROM fdw_yes123.job_snapshots
WHERE COALESCE(source_platform, 'yes123') = 'yes123';

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

CREATE VIEW gold.pbi_dim_company_v21 AS
SELECT DISTINCT ON (cust_no)
       cust_no AS "custNo", company_name AS "custName",
       co_industry AS "coIndustry", co_industry_desc AS "coIndustryDesc"
FROM gold.pbi_fact_job_scope_v21
WHERE cust_no IS NOT NULL
ORDER BY cust_no, snapshot_datetime DESC, job_no;

CREATE VIEW gold.pbi_dim_area_v21 AS
WITH area_rows AS (
    SELECT DISTINCT ON (area_key)
           area_key, job_addr_no, job_addr_no_desc, job_address
    FROM gold.pbi_fact_job_scope_v21
    WHERE area_key IS NOT NULL
    ORDER BY area_key, CASE WHEN source_platform = '104' THEN 0 ELSE 1 END, job_no
), effective_coordinates AS (
    SELECT encode(convert_to(f.area_key, 'UTF8'), 'hex') AS "areaKey",
           f.job_addr_no AS "jobAddrNo", f.job_addr_no_desc AS "jobAddrNoDesc",
           f.job_address AS "jobAddress",
           CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.latitude
                WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.latitude END AS lat,
           CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.longitude
                WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.longitude END AS lon
    FROM area_rows AS f
    LEFT JOIN silver.area_dimension AS a USING (area_key)
    LEFT JOIN silver.address_geocodes AS g USING (area_key)
)
SELECT "areaKey", "jobAddrNo", "jobAddrNoDesc", "jobAddress", lat, lon,
       CASE
           WHEN lat IS NULL OR lon IS NULL THEN '未判定'
           WHEN (lat BETWEEN 21.8 AND 25.5 AND lon BETWEEN 119.2 AND 122.1)
             OR (lat BETWEEN 24.3 AND 24.6 AND lon BETWEEN 118.1 AND 118.6)
             OR (lat BETWEEN 25.9 AND 26.5 AND lon BETWEEN 119.8 AND 120.2)
             OR (lat BETWEEN 20.5 AND 20.9 AND lon BETWEEN 116.4 AND 116.9)
             OR (lat BETWEEN 10.3 AND 10.5 AND lon BETWEEN 114.3 AND 114.5)
               THEN '國內'
           ELSE '國外(台灣地區之外)'
       END AS "jobLocationScope"
FROM effective_coordinates;

CREATE VIEW gold.pbi_bridge_job_skill_v21 AS
SELECT DISTINCT s.job_no AS "jobNo", s.skill_code AS "skillCode",
       s.skill_description AS "skillDescription"
FROM silver.job_skill_snapshots AS s
JOIN gold.pbi_fact_job_scope_v21 AS f
  USING (series_key, snapshot_date, batch_id, job_no)
WHERE f.source_platform = '104';

CREATE VIEW gold.pbi_dim_skill_v21 AS
SELECT DISTINCT d.skill_code AS "skillCode", d.skill_description AS "skillDescription"
FROM gold.pbi_bridge_job_skill_v21 AS b
JOIN silver.skill_dimension AS d ON d.skill_code = b."skillCode";

CREATE VIEW gold.pbi_bridge_job_category_v21 AS
SELECT DISTINCT s.job_no AS "jobNo", s.job_cat_code AS "jobCatCode",
       d.job_cat_description AS "jobCatDescription"
FROM silver.job_category_snapshots AS s
JOIN gold.pbi_fact_job_scope_v21 AS f
  USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.category_dimension AS d USING (job_cat_code)
WHERE f.source_platform = '104'
UNION ALL
SELECT DISTINCT s.job_no AS "jobNo", s.job_cat_code AS "jobCatCode",
       d.job_cat_description AS "jobCatDescription"
FROM fdw_yes123.job_category_snapshots AS s
JOIN gold.pbi_fact_job_scope_v21 AS f
  USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.category_dimension AS d USING (job_cat_code)
WHERE f.source_platform = 'yes123';

CREATE VIEW gold.pbi_dim_job_category_v21 AS
SELECT DISTINCT "jobCatCode", "jobCatDescription"
FROM gold.pbi_bridge_job_category_v21;

CREATE VIEW gold.pbi_dim_date_v21 AS
WITH local_today AS (
    SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Taipei')::date AS today
), source_bounds AS (
    SELECT MIN(observed_date) AS start_date, MAX(observed_date) AS end_date
    FROM (
        SELECT "appearDate" AS observed_date FROM gold.pbi_fact_jobs_v21
        UNION ALL
        SELECT "snapshotDate" FROM gold.pbi_fact_job_snapshots_v21
    ) AS source_dates
), bounds AS (
    SELECT COALESCE(s.start_date, date_trunc('year', t.today)::date) AS start_date,
           COALESCE(s.end_date,
                    (date_trunc('year', t.today) + interval '1 year' - interval '1 day')::date) AS end_date
    FROM local_today AS t CROSS JOIN source_bounds AS s
), calendar AS (
    SELECT generate_series(start_date, end_date, interval '1 day')::date AS calendar_date
    FROM bounds
)
SELECT calendar_date AS "Date",
       EXTRACT(YEAR FROM calendar_date)::integer AS "Year",
       EXTRACT(MONTH FROM calendar_date)::integer AS "MonthNo",
       to_char(calendar_date, 'YYYY-MM') AS "Month",
       EXTRACT(QUARTER FROM calendar_date)::integer AS "QuarterNo",
       'Q' || EXTRACT(QUARTER FROM calendar_date)::integer::text AS "Quarter",
       EXTRACT(DAY FROM calendar_date)::integer AS "Day"
FROM calendar;

INSERT INTO bronze.schema_migrations(version) VALUES (21)
ON CONFLICT (version) DO NOTHING;

COMMIT;
