-- ============================================================================
-- Migration: 019_multi_platform_isolation.sql
-- Purpose: Introduce platform isolation, surrogate keys, and crosswalk tables
--          to prevent namespace collisions between 104 and yes123.
-- Backward Compatibility: Zero-breaking-change to existing 104 views and PBIR.
-- ============================================================================

-- 1. Bronze Layer Platform Tagging
ALTER TABLE bronze.capture_batches 
    ADD COLUMN IF NOT EXISTS source_platform TEXT NOT NULL DEFAULT '104',
    ADD COLUMN IF NOT EXISTS code_kind TEXT NOT NULL DEFAULT '104_JOBCAT',
    ADD COLUMN IF NOT EXISTS native_search_code TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_capture_batches_platform'
    ) THEN
        ALTER TABLE bronze.capture_batches
            ADD CONSTRAINT chk_capture_batches_platform
            CHECK (source_platform IN ('104', 'yes123'));
    END IF;
END $$;

ALTER TABLE bronze.raw_job_rows 
    ADD COLUMN IF NOT EXISTS source_platform TEXT NOT NULL DEFAULT '104',
    ADD COLUMN IF NOT EXISTS native_job_id TEXT;

-- 2. Silver Layer Surrogate Keys & Namespace Decoupling
ALTER TABLE silver.job_current 
    ADD COLUMN IF NOT EXISTS source_platform TEXT NOT NULL DEFAULT '104',
    ADD COLUMN IF NOT EXISTS native_job_id TEXT,
    ADD COLUMN IF NOT EXISTS source_job_key TEXT;

UPDATE silver.job_current
SET native_job_id = job_no,
    source_job_key = '104:' || job_no
WHERE source_job_key IS NULL;

ALTER TABLE silver.job_snapshots 
    ADD COLUMN IF NOT EXISTS source_platform TEXT NOT NULL DEFAULT '104',
    ADD COLUMN IF NOT EXISTS native_job_id TEXT,
    ADD COLUMN IF NOT EXISTS source_job_key TEXT;

UPDATE silver.job_snapshots
SET native_job_id = job_no,
    source_job_key = '104:' || job_no
WHERE source_job_key IS NULL;

-- 3. Category Crosswalk (Mapping non-104 category trees to Canonical baseline)
CREATE TABLE IF NOT EXISTS silver.category_crosswalk (
    source_platform TEXT NOT NULL,
    native_category_code TEXT NOT NULL,
    native_category_name TEXT NOT NULL,
    canonical_job_cat_code BIGINT REFERENCES silver.category_dimension(job_cat_code),
    mapping_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (mapping_status IN (
        'CONFIRMED', 'PENDING_REVIEW', 'UNMAPPED', 'BLOCKED')),
    match_confidence NUMERIC(3, 2) NOT NULL DEFAULT 1.0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_platform, native_category_code)
);

-- Seed probe-verified yes123 category
INSERT INTO silver.category_crosswalk
    (source_platform, native_category_code, native_category_name, canonical_job_cat_code, mapping_status, match_confidence, notes)
VALUES
    ('yes123', '2_1006_0002_0003', '軟體相關專案管理師', 2007001001, 'CONFIRMED', 1.00, 'Probe verified: maps to software PM/engineering')
ON CONFLICT (source_platform, native_category_code) DO NOTHING;

-- 4. Master Company Entity Resolution Tables
CREATE TABLE IF NOT EXISTS silver.company_master (
    company_master_sk TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    business_tax_id CHAR(8) CHECK (business_tax_id IS NULL OR business_tax_id ~ '^[0-9]{8}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.company_source_mapping (
    source_platform TEXT NOT NULL,
    native_company_id TEXT NOT NULL,
    raw_company_name TEXT NOT NULL,
    company_master_sk TEXT NOT NULL REFERENCES silver.company_master(company_master_sk),
    match_method TEXT NOT NULL CHECK (match_method IN ('TAX_ID_EXACT', 'NORMALIZED_NAME', 'MANUAL_OVERRIDE', 'PLATFORM_DEFAULT')),
    matched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_platform, native_company_id)
);

-- 5. Register yes123 Pacing Channel
INSERT INTO bronze.capture_request_state
    (channel, minimum_interval_seconds, interval_seconds, maximum_interval_seconds)
VALUES ('yes123_jobs', 2.0, 2.0, 10.0)
ON CONFLICT (channel) DO NOTHING;

-- 6. Gold Views Non-Breaking Expansion (Append new columns to the end)
CREATE OR REPLACE VIEW gold.pbi_fact_job_scope AS
WITH latest_category_observations AS (
    SELECT DISTINCT ON (s.job_no)
           s.series_key, s.snapshot_date, s.batch_id, s.job_no, s.cust_no, s.area_key,
           s.salary_low, s.salary_high, s.appear_date, s.snapshot_datetime,
           s.source_keyword, s.source_area, s.source_jobcat,
           COALESCE(s.source_platform, '104') AS source_platform,
           COALESCE(s.native_job_id, s.job_no) AS native_job_id,
           COALESCE(s.source_job_key, '104:' || s.job_no) AS source_job_key
    FROM gold.latest_job_snapshots AS s
    WHERE s.source_jobcat IS NOT NULL
      AND COALESCE(s.source_keyword, '') = ''
    ORDER BY s.job_no, s.snapshot_datetime DESC, s.series_key, s.batch_id DESC
)
SELECT s.series_key, s.snapshot_date, s.batch_id, s.job_no, s.cust_no, s.area_key,
       s.salary_low, s.salary_high, s.appear_date,
       s.snapshot_datetime AT TIME ZONE 'Asia/Taipei' AS snapshot_datetime,
       s.source_keyword, s.source_area, s.source_jobcat,
       j.job_name, j.desc_snippet, j.job_link,
       c.company_name, c.co_industry, c.co_industry_desc,
       a.job_addr_no, a.job_addr_no_desc, a.job_address,
       s.source_platform, s.native_job_id, s.source_job_key
FROM latest_category_observations AS s
JOIN silver.job_current AS j ON j.job_no = s.job_no
JOIN silver.company_dimension AS c ON c.cust_no = s.cust_no
LEFT JOIN silver.area_dimension AS a ON a.area_key = s.area_key;

CREATE OR REPLACE VIEW gold.pbi_fact_jobs AS
SELECT job_no AS "jobNo", cust_no AS "custNo",
       encode(convert_to(area_key, 'UTF8'), 'hex') AS "areaKey",
       job_name AS "jobName", desc_snippet AS "descSnippet",
       job_address AS "jobAddress", job_addr_no_desc AS "jobAddrNoDesc",
       salary_low AS "salaryLow", salary_high AS "salaryHigh",
       appear_date AS "appearDate", job_link AS "jobLink",
       snapshot_date AS "snapshotDate", snapshot_datetime AS "snapshotDateTime",
       source_keyword AS "sourceKeyword", source_area AS "sourceArea",
       source_platform AS "sourcePlatform",
       native_job_id AS "nativeJobId",
       source_job_key AS "sourceJobKey"
FROM gold.pbi_fact_job_scope;

-- 7. Record Migration Version
INSERT INTO bronze.schema_migrations(version) VALUES (19) ON CONFLICT (version) DO NOTHING;
