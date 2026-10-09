-- Migration 020: Federated FDW Architecture between jobwant_104 and jobwant_yes123

CREATE EXTENSION IF NOT EXISTS postgres_fdw;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_foreign_server WHERE srvname = 'srv_jobwant_yes123') THEN
        CREATE SERVER srv_jobwant_yes123
            FOREIGN DATA WRAPPER postgres_fdw
            OPTIONS (host '127.0.0.1', port '5432', dbname 'jobwant_yes123', fetch_size '10000', use_remote_estimate 'true');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_user_mappings WHERE srvname = 'srv_jobwant_yes123' AND usename = 'pbi_admin'
    ) THEN
        CREATE USER MAPPING FOR pbi_admin
            SERVER srv_jobwant_yes123
            OPTIONS (user 'pbi_admin', password '64634F989C4DBB3AFCD1E393003BF25B709266E288D52C71958EAD58FA381D89');
    END IF;
END $$;

DROP SCHEMA IF EXISTS fdw_yes123 CASCADE;
CREATE SCHEMA fdw_yes123;

IMPORT FOREIGN SCHEMA silver
    LIMIT TO (job_current, job_snapshots, company_dimension, area_dimension, job_category_snapshots, category_crosswalk)
    FROM SERVER srv_jobwant_yes123
    INTO fdw_yes123;

CREATE OR REPLACE VIEW gold.pbi_fact_job_scope AS
WITH latest_104_observations AS (
    SELECT DISTINCT ON (s_1.job_no) s_1.series_key,
        s_1.snapshot_date,
        s_1.batch_id,
        s_1.job_no,
        s_1.cust_no,
        s_1.area_key,
        s_1.salary_low,
        s_1.salary_high,
        s_1.appear_date,
        s_1.snapshot_datetime,
        s_1.source_keyword,
        s_1.source_area,
        s_1.source_jobcat,
        '104'::text AS source_platform,
        COALESCE(s_1.native_job_id, s_1.job_no) AS native_job_id,
        COALESCE(s_1.source_job_key, '104:'::text || s_1.job_no) AS source_job_key
    FROM gold.latest_job_snapshots s_1
    WHERE s_1.source_jobcat IS NOT NULL
      AND COALESCE(s_1.source_keyword, ''::text) = ''::text
      AND COALESCE(s_1.source_platform, '104') = '104'
    ORDER BY s_1.job_no, s_1.snapshot_datetime DESC, s_1.series_key, s_1.batch_id DESC
),
obs_104 AS (
    SELECT s.series_key,
        s.snapshot_date,
        s.batch_id,
        s.job_no,
        s.cust_no,
        s.area_key,
        s.salary_low,
        s.salary_high,
        s.appear_date,
        (s.snapshot_datetime AT TIME ZONE 'Asia/Taipei'::text) AS snapshot_datetime,
        s.source_keyword,
        s.source_area,
        s.source_jobcat,
        j.job_name,
        j.desc_snippet,
        j.job_link,
        c.company_name,
        c.co_industry,
        c.co_industry_desc,
        a.job_addr_no,
        a.job_addr_no_desc,
        a.job_address,
        '104'::text AS source_platform,
        s.native_job_id,
        s.source_job_key
    FROM latest_104_observations s
    JOIN silver.job_current j ON j.job_no = s.job_no
    JOIN silver.company_dimension c ON c.cust_no = s.cust_no
    LEFT JOIN silver.area_dimension a ON a.area_key = s.area_key
),
obs_yes123 AS (
    SELECT s.series_key,
        s.snapshot_date,
        s.batch_id,
        s.job_no,
        s.cust_no,
        s.area_key,
        s.salary_low,
        s.salary_high,
        s.appear_date,
        (s.snapshot_datetime AT TIME ZONE 'Asia/Taipei'::text) AS snapshot_datetime,
        s.source_keyword,
        s.source_area,
        s.source_jobcat,
        j.job_name,
        j.desc_snippet,
        j.job_link,
        c.company_name,
        c.co_industry,
        c.co_industry_desc,
        a.job_addr_no,
        a.job_addr_no_desc,
        a.job_address,
        'yes123'::text AS source_platform,
        COALESCE(s.native_job_id, j.native_job_id) AS native_job_id,
        COALESCE(s.source_job_key, j.source_job_key) AS source_job_key
    FROM fdw_yes123.job_snapshots s
    JOIN fdw_yes123.job_current j ON j.job_no = s.job_no
    JOIN fdw_yes123.company_dimension c ON c.cust_no = s.cust_no
    LEFT JOIN fdw_yes123.area_dimension a ON a.area_key = s.area_key
)
SELECT * FROM obs_104
UNION ALL
SELECT * FROM obs_yes123;

CREATE OR REPLACE VIEW gold.pbi_fact_jobs AS
SELECT job_no AS "jobNo",
       cust_no AS "custNo",
       encode(convert_to(area_key, 'UTF8'::name), 'hex'::text) AS "areaKey",
       job_name AS "jobName",
       desc_snippet AS "descSnippet",
       job_address AS "jobAddress",
       job_addr_no_desc AS "jobAddrNoDesc",
       salary_low AS "salaryLow",
       salary_high AS "salaryHigh",
       appear_date AS "appearDate",
       job_link AS "jobLink",
       snapshot_date AS "snapshotDate",
       snapshot_datetime AS "snapshotDateTime",
       source_keyword AS "sourceKeyword",
       source_area AS "sourceArea",
       source_platform AS "sourcePlatform",
       native_job_id AS "nativeJobId",
       source_job_key AS "sourceJobKey"
FROM gold.pbi_fact_job_scope;

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category AS
SELECT s.job_no AS "jobNo",
       s.job_cat_code AS "jobCatCode",
       d.job_cat_description AS "jobCatDescription"
FROM silver.job_category_snapshots s
JOIN gold.pbi_fact_job_scope f USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.category_dimension d USING (job_cat_code)
WHERE f.source_platform = '104'
UNION ALL
SELECT s.job_no AS "jobNo",
       s.job_cat_code AS "jobCatCode",
       d.job_cat_description AS "jobCatDescription"
FROM fdw_yes123.job_category_snapshots s
JOIN gold.pbi_fact_job_scope f USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.category_dimension d USING (job_cat_code)
WHERE f.source_platform = 'yes123';

INSERT INTO bronze.schema_migrations (version) VALUES (20) ON CONFLICT (version) DO NOTHING;
