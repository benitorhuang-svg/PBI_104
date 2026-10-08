CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS bronze.schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bronze.capture_batches (
    batch_id TEXT PRIMARY KEY,
    series_key TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    snapshot_datetime TIMESTAMPTZ NOT NULL,
    source_jobcat TEXT,
    request JSONB NOT NULL,
    manifest_sha256 CHAR(64) NOT NULL CHECK (length(manifest_sha256) = 64),
    manifest JSONB NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    capture_status TEXT NOT NULL DEFAULT 'COMPLETE' CHECK (capture_status IN (
        'COMPLETE', 'PAGE_TOTAL_MISMATCH', 'SILVER_NORMALIZATION_BLOCKED',
        'PAGE_TOTAL_MISMATCH_AND_SILVER_NORMALIZATION_BLOCKED')),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (series_key, snapshot_date, batch_id)
);

CREATE TABLE IF NOT EXISTS bronze.raw_job_rows (
    batch_id TEXT NOT NULL REFERENCES bronze.capture_batches(batch_id),
    source_page INTEGER NOT NULL CHECK (source_page >= 1),
    row_index INTEGER NOT NULL CHECK (row_index >= 0),
    job_no TEXT,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    payload_source_json TEXT,
    payload_quality_flags JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(payload_quality_flags) = 'array'),
    PRIMARY KEY (batch_id, source_page, row_index)
);

CREATE TABLE IF NOT EXISTS bronze.capture_pages (
    batch_id TEXT NOT NULL REFERENCES bronze.capture_batches(batch_id),
    source_page INTEGER NOT NULL CHECK (source_page >= 1),
    response_sha256 CHAR(64) NOT NULL CHECK (length(response_sha256) = 64),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    response_metadata JSONB NOT NULL CHECK (jsonb_typeof(response_metadata) = 'object'),
    technical_metadata JSONB NOT NULL CHECK (jsonb_typeof(technical_metadata) = 'object'),
    PRIMARY KEY (batch_id, source_page)
);

CREATE TABLE IF NOT EXISTS bronze.job_category_catalogs (
    catalog_sha256 CHAR(64) PRIMARY KEY CHECK (length(catalog_sha256) = 64),
    source_url TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    root_count INTEGER NOT NULL CHECK (root_count >= 0),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'array'),
    manifest JSONB NOT NULL CHECK (jsonb_typeof(manifest) = 'object'),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bronze.job_category_catalog_rows (
    catalog_sha256 CHAR(64) NOT NULL REFERENCES bronze.job_category_catalogs(catalog_sha256),
    job_cat_code BIGINT NOT NULL,
    parent_job_cat_code BIGINT,
    category_name TEXT NOT NULL,
    english_name TEXT,
    hierarchy_depth SMALLINT NOT NULL CHECK (hierarchy_depth >= 0),
    path_codes JSONB NOT NULL CHECK (jsonb_typeof(path_codes) = 'array'),
    is_leaf BOOLEAN NOT NULL,
    PRIMARY KEY (catalog_sha256, job_cat_code)
);

CREATE TABLE IF NOT EXISTS silver.company_dimension (
    cust_no TEXT PRIMARY KEY,
    company_name TEXT,
    co_industry INTEGER,
    co_industry_desc TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.area_dimension (
    area_key TEXT PRIMARY KEY,
    job_addr_no BIGINT,
    job_addr_no_desc TEXT,
    job_address TEXT,
    latitude NUMERIC,
    longitude NUMERIC
);

CREATE TABLE IF NOT EXISTS silver.address_geocodes (
    area_key TEXT PRIMARY KEY REFERENCES silver.area_dimension(area_key),
    address_hash CHAR(64) NOT NULL CHECK (length(address_hash) = 64),
    normalized_address TEXT NOT NULL,
    input_address TEXT NOT NULL,
    matched_address TEXT,
    canonical_address TEXT,
    standardization_version TEXT,
    google_maps_search_url TEXT,
    latitude NUMERIC,
    longitude NUMERIC,
    match_level TEXT NOT NULL CHECK (match_level IN (
        'EXACT_TEXT', 'ADDRESS_STANDARDIZED', 'ADDRESS_VARIANT',
        'STREET_FALLBACK', 'POI_ALIAS', 'NOT_FOUND')),
    strategy TEXT,
    geocoder_name TEXT NOT NULL DEFAULT 'WGS84_TWD97',
    geocoded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((latitude IS NULL) = (longitude IS NULL)),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CHECK ((match_level = 'NOT_FOUND') = (latitude IS NULL))
);

CREATE INDEX IF NOT EXISTS ix_address_geocodes_address_hash
    ON silver.address_geocodes(address_hash);

CREATE TABLE IF NOT EXISTS silver.skill_dimension (
    skill_code TEXT PRIMARY KEY,
    skill_description TEXT
);

CREATE TABLE IF NOT EXISTS silver.category_dimension (
    job_cat_code BIGINT PRIMARY KEY,
    job_cat_description TEXT NOT NULL DEFAULT 'BLOCKED',
    job_cat_english_name TEXT,
    parent_job_cat_code BIGINT,
    hierarchy_depth SMALLINT,
    path_codes JSONB,
    is_leaf BOOLEAN,
    catalog_sha256 CHAR(64)
);

CREATE TABLE IF NOT EXISTS silver.job_current (
    job_no TEXT PRIMARY KEY,
    cust_no TEXT NOT NULL REFERENCES silver.company_dimension(cust_no),
    job_name TEXT,
    description TEXT,
    desc_snippet TEXT,
    area_key TEXT REFERENCES silver.area_dimension(area_key),
    salary_low NUMERIC,
    salary_high NUMERIC,
    salary_low_raw TEXT,
    salary_high_raw TEXT,
    appear_date DATE,
    appear_date_raw TEXT,
    apply_cnt BIGINT,
    remote_work_type BIGINT,
    job_link TEXT,
    first_seen_date DATE NOT NULL,
    last_seen_date DATE NOT NULL,
    last_observed_at TIMESTAMPTZ NOT NULL,
    source_series_key TEXT NOT NULL,
    source_keyword TEXT,
    source_jobcat TEXT,
    source_area TEXT,
    quality_issues JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.job_snapshots (
    series_key TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    batch_id TEXT NOT NULL REFERENCES bronze.capture_batches(batch_id),
    job_no TEXT NOT NULL REFERENCES silver.job_current(job_no),
    snapshot_datetime TIMESTAMPTZ NOT NULL,
    cust_no TEXT NOT NULL,
    area_key TEXT,
    salary_low NUMERIC,
    salary_high NUMERIC,
    salary_low_raw TEXT,
    salary_high_raw TEXT,
    appear_date DATE,
    appear_date_raw TEXT,
    apply_cnt BIGINT,
    remote_work_type BIGINT,
    source_keyword TEXT,
    source_jobcat TEXT,
    source_area TEXT,
    source_page INTEGER NOT NULL,
    source_page_size INTEGER,
    quality_issues JSONB NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (series_key, snapshot_date, batch_id, job_no)
);

CREATE TABLE IF NOT EXISTS silver.job_salary_observations (
    series_key TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    batch_id TEXT NOT NULL,
    job_no TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('API_FIELDS', 'DESCRIPTION')),
    observation_index INTEGER NOT NULL CHECK (observation_index >= 0),
    raw_value_min TEXT,
    raw_value_max TEXT,
    amount_min NUMERIC CHECK (amount_min IS NULL OR amount_min >= 0),
    amount_max NUMERIC CHECK (amount_max IS NULL OR amount_max >= 0),
    currency_code CHAR(3),
    currency_basis TEXT NOT NULL CHECK (currency_basis IN (
        'EXPLICIT_TEXT', 'PLATFORM_DEFAULT', 'UNKNOWN')),
    pay_period TEXT NOT NULL CHECK (pay_period IN (
        'HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR', 'UNKNOWN')),
    range_kind TEXT NOT NULL CHECK (range_kind IN (
        'RANGE', 'FIXED', 'MIN_ONLY', 'MAX_ONLY', 'NEGOTIABLE', 'NOT_DISCLOSED', 'UNRESOLVED')),
    compensation_component TEXT NOT NULL CHECK (compensation_component IN (
        'BASE', 'VARIABLE', 'UNKNOWN')),
    evidence_text TEXT,
    evidence_start INTEGER CHECK (evidence_start IS NULL OR evidence_start >= 0),
    evidence_end INTEGER CHECK (evidence_end IS NULL OR evidence_end >= evidence_start),
    parse_status TEXT NOT NULL CHECK (parse_status IN (
        'PARSED', 'NEEDS_REVIEW', 'NEGOTIABLE', 'NOT_DISCLOSED',
        'API_UNIT_UNMAPPED', 'SENTINEL_CANDIDATE')),
    quality_flags JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(quality_flags) = 'array'),
    confidence NUMERIC(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    parser_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (series_key, snapshot_date, batch_id, job_no, source_kind, observation_index),
    FOREIGN KEY (series_key, snapshot_date, batch_id, job_no)
        REFERENCES silver.job_snapshots(series_key, snapshot_date, batch_id, job_no),
    CHECK (amount_min IS NULL OR amount_max IS NULL OR amount_min <= amount_max),
    CHECK ((evidence_start IS NULL AND evidence_end IS NULL) OR
           (evidence_start IS NOT NULL AND evidence_end IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS silver.job_skill_snapshots (
    series_key TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    batch_id TEXT NOT NULL REFERENCES bronze.capture_batches(batch_id),
    job_no TEXT NOT NULL REFERENCES silver.job_current(job_no),
    skill_code TEXT NOT NULL REFERENCES silver.skill_dimension(skill_code),
    skill_description TEXT,
    PRIMARY KEY (series_key, snapshot_date, batch_id, job_no, skill_code)
);

CREATE TABLE IF NOT EXISTS silver.job_category_snapshots (
    series_key TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    batch_id TEXT NOT NULL REFERENCES bronze.capture_batches(batch_id),
    job_no TEXT NOT NULL REFERENCES silver.job_current(job_no),
    job_cat_code BIGINT NOT NULL REFERENCES silver.category_dimension(job_cat_code),
    PRIMARY KEY (series_key, snapshot_date, batch_id, job_no, job_cat_code)
);

CREATE INDEX IF NOT EXISTS ix_raw_job_rows_job ON bronze.raw_job_rows(job_no);
CREATE INDEX IF NOT EXISTS ix_job_snapshots_date ON silver.job_snapshots(snapshot_date, job_no);
CREATE INDEX IF NOT EXISTS ix_job_snapshots_series ON silver.job_snapshots(series_key, snapshot_date);
CREATE INDEX IF NOT EXISTS ix_salary_observations_period
    ON silver.job_salary_observations(pay_period, currency_code, parse_status);
CREATE INDEX IF NOT EXISTS ix_salary_observations_job
    ON silver.job_salary_observations(job_no, snapshot_date);
CREATE INDEX IF NOT EXISTS ix_job_skills_skill ON silver.job_skill_snapshots(skill_code, snapshot_date);
CREATE INDEX IF NOT EXISTS ix_job_categories_category ON silver.job_category_snapshots(job_cat_code, snapshot_date);

INSERT INTO bronze.schema_migrations(version) VALUES (1) ON CONFLICT (version) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND table_name = 'area_dimension'
          AND column_name = 'job_addr_no'
          AND data_type <> 'bigint'
    ) THEN
        ALTER TABLE silver.area_dimension ALTER COLUMN job_addr_no TYPE BIGINT;
    END IF;
END
$$;
INSERT INTO bronze.schema_migrations(version) VALUES (2) ON CONFLICT (version) DO NOTHING;

ALTER TABLE silver.category_dimension ADD COLUMN IF NOT EXISTS job_cat_english_name TEXT;
ALTER TABLE silver.category_dimension ADD COLUMN IF NOT EXISTS parent_job_cat_code BIGINT;
ALTER TABLE silver.category_dimension ADD COLUMN IF NOT EXISTS hierarchy_depth SMALLINT;
ALTER TABLE silver.category_dimension ADD COLUMN IF NOT EXISTS path_codes JSONB;
ALTER TABLE silver.category_dimension ADD COLUMN IF NOT EXISTS is_leaf BOOLEAN;
ALTER TABLE silver.category_dimension ADD COLUMN IF NOT EXISTS catalog_sha256 CHAR(64);
ALTER TABLE silver.job_current ADD COLUMN IF NOT EXISTS source_jobcat TEXT;
ALTER TABLE silver.job_snapshots ADD COLUMN IF NOT EXISTS source_jobcat TEXT;
INSERT INTO bronze.schema_migrations(version) VALUES (3) ON CONFLICT (version) DO NOTHING;

ALTER TABLE bronze.capture_batches ADD COLUMN IF NOT EXISTS capture_status TEXT NOT NULL DEFAULT 'COMPLETE'
    CHECK (capture_status IN ('COMPLETE', 'PAGE_TOTAL_MISMATCH', 'SILVER_NORMALIZATION_BLOCKED',
                              'PAGE_TOTAL_MISMATCH_AND_SILVER_NORMALIZATION_BLOCKED'));
INSERT INTO bronze.schema_migrations(version) VALUES (4) ON CONFLICT (version) DO NOTHING;
INSERT INTO bronze.schema_migrations(version) VALUES (5) ON CONFLICT (version) DO NOTHING;
INSERT INTO bronze.schema_migrations(version) VALUES (6) ON CONFLICT (version) DO NOTHING;

ALTER TABLE silver.address_geocodes ADD COLUMN IF NOT EXISTS canonical_address TEXT;
ALTER TABLE silver.address_geocodes ADD COLUMN IF NOT EXISTS standardization_version TEXT;
ALTER TABLE silver.address_geocodes ADD COLUMN IF NOT EXISTS google_maps_search_url TEXT;
ALTER TABLE silver.address_geocodes DROP CONSTRAINT IF EXISTS address_geocodes_match_level_check;
ALTER TABLE silver.address_geocodes ADD CONSTRAINT address_geocodes_match_level_check
    CHECK (match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED', 'ADDRESS_VARIANT',
                           'STREET_FALLBACK', 'POI_ALIAS', 'NOT_FOUND'));
INSERT INTO bronze.schema_migrations(version) VALUES (7) ON CONFLICT (version) DO NOTHING;

CREATE OR REPLACE VIEW gold.capture_history AS
SELECT batch_id, series_key, snapshot_date, snapshot_datetime,
       request->>'keyword' AS search_keyword,
       request->>'area' AS search_area,
       row_count, imported_at,
       request->>'jobcat' AS search_jobcat, capture_status
FROM bronze.capture_batches;

CREATE OR REPLACE VIEW gold.latest_job_snapshots AS
WITH latest_batches AS (
    SELECT DISTINCT ON (series_key, snapshot_date) batch_id, series_key, snapshot_date
    FROM bronze.capture_batches
    WHERE capture_status = 'COMPLETE'
    ORDER BY series_key, snapshot_date, snapshot_datetime DESC, batch_id DESC
)
SELECT s.*
FROM silver.job_snapshots AS s
JOIN latest_batches AS b USING (series_key, snapshot_date, batch_id);

CREATE OR REPLACE VIEW gold.pbi_job_snapshots AS
SELECT series_key, snapshot_date,
       snapshot_datetime AT TIME ZONE 'Asia/Taipei' AS snapshot_datetime,
       job_no, cust_no, salary_low, salary_high, appear_date,
       source_keyword, source_area
FROM gold.latest_job_snapshots;
INSERT INTO bronze.schema_migrations(version) VALUES (8) ON CONFLICT (version) DO NOTHING;

CREATE OR REPLACE VIEW gold.latest_job_salary_observations AS
SELECT o.*
FROM silver.job_salary_observations AS o
JOIN gold.latest_job_snapshots AS s
  USING (series_key, snapshot_date, batch_id, job_no);

CREATE OR REPLACE VIEW gold.latest_observed_jobs AS
SELECT j.job_no, j.cust_no, j.job_name, j.description, j.desc_snippet, j.area_key,
       j.salary_low, j.salary_high, j.salary_low_raw, j.salary_high_raw,
       j.appear_date, j.appear_date_raw, j.apply_cnt, j.remote_work_type, j.job_link,
       j.first_seen_date, j.last_seen_date, j.last_observed_at, j.source_series_key,
       j.source_keyword, j.source_area, j.quality_issues, j.updated_at,
       c.company_name, c.co_industry, c.co_industry_desc,
       a.job_addr_no, a.job_addr_no_desc, a.job_address, a.latitude, a.longitude,
       j.source_jobcat,
       g.match_level AS geocode_match_level, g.matched_address AS geocode_matched_address,
       g.latitude AS geocode_latitude, g.longitude AS geocode_longitude,
       CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.latitude
            WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.latitude END AS latitude_effective,
       CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.longitude
            WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.longitude END AS longitude_effective,
       CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN '104_API'
            WHEN g.match_level = 'EXACT_TEXT' THEN 'WGS84_TWD97_EXACT_TEXT'
            WHEN g.match_level = 'ADDRESS_STANDARDIZED' THEN 'WGS84_TWD97_TAIWAN_STANDARD'
            WHEN g.match_level IN ('ADDRESS_VARIANT', 'STREET_FALLBACK', 'POI_ALIAS')
                THEN 'WGS84_TWD97_REVIEW'
            ELSE 'MISSING' END AS coordinate_source,
       g.canonical_address AS geocode_canonical_address,
       g.google_maps_search_url
FROM silver.job_current AS j
LEFT JOIN silver.company_dimension AS c USING (cust_no)
LEFT JOIN silver.area_dimension AS a USING (area_key)
LEFT JOIN silver.address_geocodes AS g USING (area_key);

CREATE OR REPLACE VIEW gold.area_geocodes AS
SELECT a.area_key, a.latitude AS api_latitude, a.longitude AS api_longitude,
       g.match_level AS geocode_match_level, g.matched_address AS geocode_matched_address,
       g.latitude AS geocode_latitude, g.longitude AS geocode_longitude,
       CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.latitude
            WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.latitude END AS latitude_effective,
       CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.longitude
            WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.longitude END AS longitude_effective,
       CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN '104_API'
            WHEN g.match_level = 'EXACT_TEXT' THEN 'WGS84_TWD97_EXACT_TEXT'
            WHEN g.match_level = 'ADDRESS_STANDARDIZED' THEN 'WGS84_TWD97_TAIWAN_STANDARD'
            WHEN g.match_level IN ('ADDRESS_VARIANT', 'STREET_FALLBACK', 'POI_ALIAS')
                THEN 'WGS84_TWD97_REVIEW'
            ELSE 'MISSING' END AS coordinate_source,
       g.canonical_address AS geocode_canonical_address,
       g.google_maps_search_url
FROM silver.area_dimension AS a
LEFT JOIN silver.address_geocodes AS g USING (area_key);

CREATE OR REPLACE VIEW gold.latest_job_skills AS
SELECT b.*
FROM silver.job_skill_snapshots AS b
JOIN (
    SELECT DISTINCT ON (series_key, snapshot_date) batch_id, series_key, snapshot_date
    FROM bronze.capture_batches
    WHERE capture_status = 'COMPLETE'
    ORDER BY series_key, snapshot_date, snapshot_datetime DESC, batch_id DESC
) AS latest USING (series_key, snapshot_date, batch_id);

CREATE OR REPLACE VIEW gold.latest_job_categories AS
SELECT b.*
FROM silver.job_category_snapshots AS b
JOIN (
    SELECT DISTINCT ON (series_key, snapshot_date) batch_id, series_key, snapshot_date
    FROM bronze.capture_batches
    WHERE capture_status = 'COMPLETE'
    ORDER BY series_key, snapshot_date, snapshot_datetime DESC, batch_id DESC
) AS latest USING (series_key, snapshot_date, batch_id);

CREATE OR REPLACE VIEW gold.pbi_fact_job_scope AS
WITH latest_category_observations AS (
    SELECT DISTINCT ON (s.job_no)
           s.series_key, s.snapshot_date, s.batch_id, s.job_no, s.cust_no, s.area_key,
           s.salary_low, s.salary_high, s.appear_date, s.snapshot_datetime,
           s.source_keyword, s.source_area, s.source_jobcat
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
       a.job_addr_no, a.job_addr_no_desc, a.job_address
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
       source_keyword AS "sourceKeyword", source_area AS "sourceArea"
FROM gold.pbi_fact_job_scope;

CREATE OR REPLACE VIEW gold.pbi_fact_job_snapshots AS
SELECT series_key AS "querySeriesKey", snapshot_date AS "snapshotDate",
       snapshot_datetime AS "snapshotDateTime", job_no AS "jobNo", cust_no AS "custNo",
       salary_low AS "salaryLow", salary_high AS "salaryHigh",
       appear_date AS "appearDate", source_keyword AS "sourceKeyword",
       source_area AS "sourceArea"
FROM gold.pbi_job_snapshots;

CREATE OR REPLACE VIEW gold.pbi_dim_company AS
SELECT DISTINCT cust_no AS "custNo", company_name AS "custName",
       co_industry AS "coIndustry", co_industry_desc AS "coIndustryDesc"
FROM gold.pbi_fact_job_scope;

CREATE OR REPLACE VIEW gold.pbi_dim_area AS
WITH area_keys AS (
    SELECT DISTINCT area_key
    FROM gold.pbi_fact_job_scope
    WHERE area_key IS NOT NULL
), effective_coordinates AS (
    SELECT encode(convert_to(a.area_key, 'UTF8'), 'hex') AS "areaKey",
           a.job_addr_no AS "jobAddrNo",
           a.job_addr_no_desc AS "jobAddrNoDesc", a.job_address AS "jobAddress",
           CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.latitude
                WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.latitude END AS lat,
           CASE WHEN a.latitude IS NOT NULL AND a.longitude IS NOT NULL THEN a.longitude
                WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED') THEN g.longitude END AS lon
    FROM area_keys AS f
    JOIN silver.area_dimension AS a USING (area_key)
    LEFT JOIN silver.address_geocodes AS g USING (area_key)
)
SELECT "areaKey", "jobAddrNo", "jobAddrNoDesc", "jobAddress", lat, lon,
       CASE
           WHEN lat IS NULL OR lon IS NULL THEN '未判定'
           -- WGS84 envelopes cover Taiwan/Penghu and the major outlying islands.
           WHEN (lat BETWEEN 21.8 AND 25.5 AND lon BETWEEN 119.2 AND 122.1)
             OR (lat BETWEEN 24.3 AND 24.6 AND lon BETWEEN 118.1 AND 118.6)
             OR (lat BETWEEN 25.9 AND 26.5 AND lon BETWEEN 119.8 AND 120.2)
             OR (lat BETWEEN 20.5 AND 20.9 AND lon BETWEEN 116.4 AND 116.9)
             OR (lat BETWEEN 10.3 AND 10.5 AND lon BETWEEN 114.3 AND 114.5)
               THEN '國內'
           ELSE '國外(台灣地區之外)'
       END AS "jobLocationScope"
FROM effective_coordinates;

CREATE OR REPLACE VIEW gold.pbi_bridge_job_skill AS
SELECT s.job_no AS "jobNo", s.skill_code AS "skillCode",
       s.skill_description AS "skillDescription"
FROM silver.job_skill_snapshots AS s
JOIN gold.pbi_fact_job_scope AS f
  USING (series_key, snapshot_date, batch_id, job_no);

CREATE OR REPLACE VIEW gold.pbi_dim_skill AS
SELECT DISTINCT d.skill_code AS "skillCode", d.skill_description AS "skillDescription"
FROM gold.pbi_bridge_job_skill AS b
JOIN silver.skill_dimension AS d ON d.skill_code = b."skillCode";

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category AS
SELECT s.job_no AS "jobNo", s.job_cat_code AS "jobCatCode",
       d.job_cat_description AS "jobCatDescription"
FROM silver.job_category_snapshots AS s
JOIN gold.pbi_fact_job_scope AS f
  USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.category_dimension AS d USING (job_cat_code);

CREATE OR REPLACE VIEW gold.pbi_dim_job_category AS
SELECT DISTINCT "jobCatCode", "jobCatDescription"
FROM gold.pbi_bridge_job_category;

CREATE OR REPLACE VIEW gold.pbi_dim_date AS
WITH local_today AS (
    SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Taipei')::date AS today
), source_bounds AS (
    SELECT MIN(observed_date) AS start_date, MAX(observed_date) AS end_date
    FROM (
        SELECT "appearDate" AS observed_date FROM gold.pbi_fact_jobs
        UNION ALL
        SELECT "snapshotDate" FROM gold.pbi_fact_job_snapshots
    ) AS source_dates
), bounds AS (
    SELECT COALESCE(s.start_date, date_trunc('year', t.today)::date) AS start_date,
           COALESCE(s.end_date,
                    (date_trunc('year', t.today) + interval '1 year' - interval '1 day')::date) AS end_date
    FROM local_today AS t
    CROSS JOIN source_bounds AS s
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

INSERT INTO bronze.schema_migrations(version) VALUES (9) ON CONFLICT (version) DO NOTHING;

ALTER TABLE bronze.capture_batches ADD COLUMN IF NOT EXISTS source_jobcat TEXT;
UPDATE bronze.capture_batches
SET source_jobcat = NULLIF(request->>'jobcat', '')
WHERE source_jobcat IS DISTINCT FROM NULLIF(request->>'jobcat', '');
CREATE INDEX IF NOT EXISTS ix_capture_batches_date_jobcat
    ON bronze.capture_batches(snapshot_date, source_jobcat);
INSERT INTO bronze.schema_migrations(version) VALUES (10) ON CONFLICT (version) DO NOTHING;
INSERT INTO bronze.schema_migrations(version) VALUES (11) ON CONFLICT (version) DO NOTHING;
INSERT INTO bronze.schema_migrations(version) VALUES (12) ON CONFLICT (version) DO NOTHING;

CREATE TABLE IF NOT EXISTS bronze.distributed_capture_runs (
    run_id TEXT PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    snapshot_date DATE NOT NULL,
    catalog_sha256 CHAR(64) NOT NULL CHECK (length(catalog_sha256) = 64),
    category_depth INTEGER NOT NULL CHECK (category_depth BETWEEN 0 AND 2),
    area_filter TEXT,
    pagesize INTEGER NOT NULL CHECK (pagesize BETWEEN 1 AND 30),
    minimum_interval_seconds DOUBLE PRECISION NOT NULL CHECK (minimum_interval_seconds >= 0),
    worker_count INTEGER NOT NULL CHECK (worker_count >= 1),
    status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN (
        'QUEUED', 'RUNNING', 'COMPLETE', 'COMPLETE_WITH_WARNINGS', 'PARTIAL', 'BLOCKED')),
    selected_categories INTEGER NOT NULL CHECK (selected_categories >= 0),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bronze.distributed_capture_categories (
    run_id TEXT NOT NULL REFERENCES bronze.distributed_capture_runs(run_id),
    source_jobcat TEXT NOT NULL,
    category_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'PENDING' CHECK (state IN (
        'PENDING', 'LEASED', 'DONE', 'FAIL', 'DEFERRED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    batch_id TEXT,
    result JSONB CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, source_jobcat)
);

CREATE INDEX IF NOT EXISTS ix_distributed_capture_claim
    ON bronze.distributed_capture_categories(state, available_at, lease_expires_at);

CREATE TABLE IF NOT EXISTS bronze.capture_request_state (
    channel TEXT PRIMARY KEY,
    minimum_interval_seconds DOUBLE PRECISION NOT NULL CHECK (minimum_interval_seconds >= 0),
    interval_seconds DOUBLE PRECISION NOT NULL CHECK (interval_seconds >= minimum_interval_seconds),
    maximum_interval_seconds DOUBLE PRECISION NOT NULL CHECK (maximum_interval_seconds >= interval_seconds),
    success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    next_request_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    blocked_until TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    blocked_reason TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO bronze.capture_request_state
    (channel, minimum_interval_seconds, interval_seconds, maximum_interval_seconds)
VALUES ('104_jobs', 0.8, 0.8, 8.0)
ON CONFLICT (channel) DO NOTHING;

INSERT INTO bronze.schema_migrations(version) VALUES (13) ON CONFLICT (version) DO NOTHING;

CREATE OR REPLACE FUNCTION bronze.acquisition_category_warning(
    category_result JSONB,
    stored_capture_status TEXT,
    stored_pagination_status TEXT
)
RETURNS BOOLEAN
LANGUAGE SQL
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN category_result->>'status' = 'CAPTURED_WITH_WARNING' THEN TRUE
        WHEN category_result->>'status' = 'SKIPPED' THEN
            COALESCE(stored_pagination_status,
                     category_result->>'paginationStatus') IS DISTINCT FROM 'PASS'
            OR COALESCE(stored_capture_status,
                        category_result->>'captureStatus') IS DISTINCT FROM 'COMPLETE'
        ELSE FALSE
    END
$$;

CREATE OR REPLACE VIEW gold.pbi_acquisition_categories AS
WITH latest_run AS (
    SELECT run_id, status, snapshot_date, selected_categories, category_depth,
           area_filter, pagesize, worker_count, started_at, updated_at,
           minimum_interval_seconds
    FROM bronze.distributed_capture_runs
    ORDER BY created_at DESC, run_id DESC
    LIMIT 1
), request_gate AS (
    SELECT minimum_interval_seconds, interval_seconds, blocked_reason
    FROM bronze.capture_request_state
    WHERE channel = '104_jobs'
)
SELECT r.run_id AS "runId", r.status AS "runStatus",
       r.snapshot_date AS "snapshotDate",
       r.selected_categories AS "selectedCategories",
       r.category_depth AS "categoryDepth", r.area_filter AS "areaFilter",
       r.pagesize AS "pageSize", r.worker_count AS "workerCount",
       r.started_at AS "runStartedAt", r.updated_at AS "runUpdatedAt",
       COALESCE(g.minimum_interval_seconds, r.minimum_interval_seconds)
           AS "minimumRequestIntervalSeconds",
       COALESCE(g.interval_seconds, r.minimum_interval_seconds)
           AS "requestIntervalSeconds",
       CASE WHEN g.blocked_reason IS NOT NULL THEN 1 ELSE 0 END AS "gateBlocked",
       CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Taipei' AS "sourceReadAt",
       q.source_jobcat AS "categoryCode", q.category_name AS "categoryName",
       q.state AS "categoryState", q.attempts AS "attempts",
       q.updated_at AS "categoryUpdatedAt", q.result->>'status' AS "resultStatus",
       q.batch_id AS "batchId",
       quality.capture_status AS "captureStatus",
       quality.pagination_status AS "paginationStatus",
       COALESCE(b.row_count::bigint,
           CASE WHEN q.result->>'rows' ~ '^[0-9]+$'
                THEN (q.result->>'rows')::bigint END, 0) AS "jobCount",
       COALESCE(p.page_count, 0) AS "pageCount",
       quality.warning_flag AS "warningFlag",
       CASE
           WHEN child.parent_job_cat_code IS NOT NULL THEN
               COALESCE(parent.job_cat_description, 'Unnamed parent category')
                   || ' (' || child.parent_job_cat_code::text || ')'
           WHEN child.job_cat_code IS NOT NULL THEN
               child.job_cat_description || ' (' || child.job_cat_code::text || ')'
           ELSE q.category_name || ' (' || q.source_jobcat || ')'
       END AS "parentCategoryLabel",
       CASE
           WHEN child.parent_job_cat_code IS NOT NULL THEN
               child.parent_job_cat_code::text
           WHEN child.job_cat_code IS NOT NULL THEN
               child.job_cat_code::text
           ELSE q.source_jobcat
       END AS "parentCategoryCode",
       CASE
           WHEN child.parent_job_cat_code IS NOT NULL THEN
               COALESCE(parent.job_cat_description, 'Unnamed parent category')
           WHEN child.job_cat_code IS NOT NULL THEN
               COALESCE(child.job_cat_description, 'Unnamed parent category')
           ELSE COALESCE(q.category_name, 'Unnamed category')
       END AS "parentCategoryName",
       COALESCE(p.reported_job_count_min,
           CASE WHEN q.result->>'totalJobs' ~ '^[0-9]+$'
                THEN (q.result->>'totalJobs')::bigint END) AS "apiReportedJobCountMin",
       COALESCE(p.reported_job_count_max,
           CASE WHEN q.result->>'totalJobs' ~ '^[0-9]+$'
                THEN (q.result->>'totalJobs')::bigint END) AS "apiReportedJobCountMax",
       p.reported_page_count_min AS "apiReportedPageCountMin",
       p.reported_page_count_max AS "apiReportedPageCountMax",
       CASE WHEN q.state IN ('DONE', 'FAIL', 'DEFERRED') THEN 1 ELSE 0
       END AS "queueTerminalFlag",
       CASE WHEN q.state = 'DONE' AND b.batch_id IS NOT NULL
                 AND quality.pagination_status = 'PASS' THEN 1 ELSE 0
       END AS "captureCompleteFlag",
       CASE WHEN q.state = 'DONE' AND b.batch_id IS NOT NULL
                 AND quality.pagination_status = 'PASS'
                 AND quality.capture_status = 'COMPLETE' THEN 1 ELSE 0
       END AS "silverEligibleFlag",
       CASE WHEN quality.capture_status IN (
                  'SILVER_NORMALIZATION_BLOCKED',
                  'PAGE_TOTAL_MISMATCH_AND_SILVER_NORMALIZATION_BLOCKED')
            THEN 1 ELSE 0 END AS "silverBlockedFlag",
       CASE WHEN quality.warning_flag = 0 THEN NULL
             ELSE COALESCE(NULLIF(concat_ws(', ',
                 CASE WHEN quality.pagination_status IS DISTINCT FROM 'PASS'
                      THEN 'PAGE_TOTAL_MISMATCH' END,
                 CASE WHEN quality.capture_status IN (
                          'SILVER_NORMALIZATION_BLOCKED',
                          'PAGE_TOTAL_MISMATCH_AND_SILVER_NORMALIZATION_BLOCKED')
                      THEN 'SILVER_NORMALIZATION_BLOCKED' END), ''),
                 'QUALITY_STATUS_INCOMPLETE')
        END AS "warningReason"
FROM latest_run AS r
JOIN bronze.distributed_capture_categories AS q USING (run_id)
LEFT JOIN request_gate AS g ON TRUE
LEFT JOIN bronze.capture_batches AS b ON b.batch_id = q.batch_id
LEFT JOIN LATERAL (
    SELECT COALESCE(b.manifest->>'paginationStatus',
                    q.result->>'paginationStatus') AS pagination_status,
           COALESCE(b.capture_status,
                    q.result->>'captureStatus') AS capture_status,
           CASE WHEN bronze.acquisition_category_warning(
               q.result, b.capture_status, b.manifest->>'paginationStatus')
               THEN 1 ELSE 0 END AS warning_flag
) AS quality ON TRUE
LEFT JOIN silver.category_dimension AS child
    ON child.job_cat_code = CASE
        WHEN q.source_jobcat ~ '^[0-9]{1,18}$' THEN q.source_jobcat::bigint
    END
LEFT JOIN silver.category_dimension AS parent
    ON parent.job_cat_code = child.parent_job_cat_code
LEFT JOIN LATERAL (
    SELECT COUNT(*)::bigint AS page_count,
           MIN(CASE WHEN cp.response_metadata #>> '{pagination,total}' ~ '^[0-9]+$'
                    THEN (cp.response_metadata #>> '{pagination,total}')::bigint END)
               AS reported_job_count_min,
           MAX(CASE WHEN cp.response_metadata #>> '{pagination,total}' ~ '^[0-9]+$'
                    THEN (cp.response_metadata #>> '{pagination,total}')::bigint END)
               AS reported_job_count_max,
           MIN(CASE WHEN cp.response_metadata #>> '{pagination,lastPage}' ~ '^[0-9]+$'
                    THEN (cp.response_metadata #>> '{pagination,lastPage}')::bigint END)
               AS reported_page_count_min,
           MAX(CASE WHEN cp.response_metadata #>> '{pagination,lastPage}' ~ '^[0-9]+$'
                    THEN (cp.response_metadata #>> '{pagination,lastPage}')::bigint END)
               AS reported_page_count_max
    FROM bronze.capture_pages AS cp
    WHERE cp.batch_id = q.batch_id
) AS p ON TRUE;

INSERT INTO bronze.schema_migrations(version) VALUES (14) ON CONFLICT (version) DO NOTHING;

ALTER TABLE bronze.raw_job_rows ADD COLUMN IF NOT EXISTS payload_source_json TEXT;
INSERT INTO bronze.schema_migrations(version) VALUES (15) ON CONFLICT (version) DO NOTHING;

ALTER TABLE bronze.raw_job_rows ADD COLUMN IF NOT EXISTS payload_quality_flags JSONB
    NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(payload_quality_flags) = 'array');
INSERT INTO bronze.schema_migrations(version) VALUES (16) ON CONFLICT (version) DO NOTHING;
INSERT INTO bronze.schema_migrations(version) VALUES (17) ON CONFLICT (version) DO NOTHING;
INSERT INTO bronze.schema_migrations(version) VALUES (18) ON CONFLICT (version) DO NOTHING;
