-- =============================================================================
-- PBI_104 Modern Data Platform: PostgreSQL Target Architecture (Option D)
-- Medallion Storage Model: Bronze (Raw JSONB) -> Silver (Conformed) -> Gold (Star Schema)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- -----------------------------------------------------------------------------
-- 1. BRONZE LAYER: Raw Payload Immutability & Audit Trail
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.raw_job_payloads (
    job_no VARCHAR(32) NOT NULL,
    search_keyword VARCHAR(64) NOT NULL,
    batch_id VARCHAR(64) NOT NULL,
    series_key VARCHAR(64) NOT NULL,
    source_page INTEGER NOT NULL,
    raw_payload JSONB NOT NULL,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_raw_job_payloads PRIMARY KEY (job_no, search_keyword, batch_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_payload_gin ON bronze.raw_job_payloads USING GIN (raw_payload);
CREATE INDEX IF NOT EXISTS idx_raw_job_no ON bronze.raw_job_payloads (job_no);
CREATE INDEX IF NOT EXISTS idx_raw_keyword ON bronze.raw_job_payloads (search_keyword);

-- -----------------------------------------------------------------------------
-- 2. SILVER LAYER: Normalized Entities, CDC & Bridges
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.dim_company (
    cust_no VARCHAR(32) PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    co_industry INTEGER,
    co_industry_desc VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.dim_area (
    area_key VARCHAR(64) PRIMARY KEY,
    job_addr_no INTEGER,
    job_addr_no_desc VARCHAR(255),
    job_address TEXT,
    lat NUMERIC(9, 6),
    lon NUMERIC(9, 6)
);

CREATE TABLE IF NOT EXISTS silver.dim_skill (
    skill_code VARCHAR(64) PRIMARY KEY,
    skill_description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS silver.dim_job_category (
    job_cat_code BIGINT PRIMARY KEY,
    job_cat_description VARCHAR(255) DEFAULT 'BLOCKED'
);

CREATE TABLE IF NOT EXISTS silver.dim_keyword (
    search_keyword VARCHAR(64) PRIMARY KEY,
    category VARCHAR(64) DEFAULT 'General'
);

CREATE TABLE IF NOT EXISTS silver.fact_job (
    job_no VARCHAR(32) PRIMARY KEY,
    cust_no VARCHAR(32) REFERENCES silver.dim_company(cust_no),
    job_name VARCHAR(512) NOT NULL,
    description TEXT,
    desc_snippet TEXT,
    area_key VARCHAR(64) REFERENCES silver.dim_area(area_key),
    salary_low NUMERIC(12, 2),
    salary_high NUMERIC(12, 2),
    salary_low_raw VARCHAR(64),
    salary_high_raw VARCHAR(64),
    appear_date DATE,
    appear_date_raw VARCHAR(32),
    apply_cnt INTEGER,
    remote_work_type INTEGER,
    job_link TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    first_seen_at DATE NOT NULL,
    last_seen_at DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.fact_job_snapshot (
    snapshot_date DATE NOT NULL,
    job_no VARCHAR(32) NOT NULL REFERENCES silver.fact_job(job_no) ON DELETE CASCADE,
    cust_no VARCHAR(32),
    area_key VARCHAR(64),
    salary_low NUMERIC(12, 2),
    salary_high NUMERIC(12, 2),
    apply_cnt INTEGER,
    remote_work_type INTEGER,
    source_keyword VARCHAR(64),
    source_area VARCHAR(128),
    source_page INTEGER,
    source_page_size INTEGER,
    snapshot_datetime TIMESTAMP WITH TIME ZONE,
    CONSTRAINT pk_fact_job_snapshot PRIMARY KEY (snapshot_date, job_no)
);

CREATE TABLE IF NOT EXISTS silver.bridge_job_skill (
    job_no VARCHAR(32) NOT NULL REFERENCES silver.fact_job(job_no) ON DELETE CASCADE,
    skill_code VARCHAR(64) NOT NULL REFERENCES silver.dim_skill(skill_code),
    skill_description VARCHAR(255),
    CONSTRAINT pk_bridge_job_skill PRIMARY KEY (job_no, skill_code)
);

CREATE TABLE IF NOT EXISTS silver.bridge_job_category (
    job_no VARCHAR(32) NOT NULL REFERENCES silver.fact_job(job_no) ON DELETE CASCADE,
    job_cat_code BIGINT NOT NULL REFERENCES silver.dim_job_category(job_cat_code),
    job_cat_description VARCHAR(255),
    CONSTRAINT pk_bridge_job_category PRIMARY KEY (job_no, job_cat_code)
);

CREATE TABLE IF NOT EXISTS silver.bridge_job_keyword (
    job_no VARCHAR(32) NOT NULL REFERENCES silver.fact_job(job_no) ON DELETE CASCADE,
    search_keyword VARCHAR(64) NOT NULL REFERENCES silver.dim_keyword(search_keyword),
    last_matched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_bridge_job_keyword PRIMARY KEY (job_no, search_keyword)
);

-- -----------------------------------------------------------------------------
-- 3. GOLD LAYER: Star Schema Consumption Views for Power BI
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.fact_jobs AS
SELECT
    j.job_no,
    j.cust_no,
    c.company_name AS cust_name,
    c.co_industry,
    c.co_industry_desc,
    j.job_name,
    j.description,
    j.desc_snippet,
    a.job_address,
    a.job_addr_no,
    a.job_addr_no_desc,
    a.lat,
    a.lon,
    j.salary_low_raw,
    j.salary_high_raw,
    j.salary_low,
    j.salary_high,
    j.appear_date_raw,
    j.appear_date,
    j.apply_cnt,
    j.remote_work_type,
    j.area_key,
    j.job_link,
    j.is_active,
    j.first_seen_at,
    j.last_seen_at
FROM silver.fact_job j
LEFT JOIN silver.dim_company c ON j.cust_no = c.cust_no
LEFT JOIN silver.dim_area a ON j.area_key = a.area_key;

CREATE OR REPLACE VIEW gold.fact_job_snapshots AS
SELECT * FROM silver.fact_job_snapshot;

CREATE OR REPLACE VIEW gold.dim_companies AS
SELECT cust_no, company_name AS cust_name, co_industry, co_industry_desc FROM silver.dim_company;

CREATE OR REPLACE VIEW gold.dim_areas AS
SELECT area_key, job_addr_no, job_addr_no_desc, job_address, lat, lon FROM silver.dim_area;

CREATE OR REPLACE VIEW gold.dim_skills AS
SELECT skill_code, skill_description FROM silver.dim_skill;

CREATE OR REPLACE VIEW gold.dim_job_categories AS
SELECT job_cat_code, job_cat_description FROM silver.dim_job_category;

CREATE OR REPLACE VIEW gold.dim_keywords AS
SELECT search_keyword, category FROM silver.dim_keyword;

CREATE OR REPLACE VIEW gold.bridge_job_skills AS
SELECT job_no, skill_code, skill_description FROM silver.bridge_job_skill;

CREATE OR REPLACE VIEW gold.bridge_job_categories AS
SELECT job_no, job_cat_code, job_cat_description FROM silver.bridge_job_category;

CREATE OR REPLACE VIEW gold.bridge_job_keywords AS
SELECT job_no, search_keyword FROM silver.bridge_job_keyword;
