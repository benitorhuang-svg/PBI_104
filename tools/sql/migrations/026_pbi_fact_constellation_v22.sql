-- Migration 026: introduce grain-correct v22 Power BI job facts.
-- STATUS: DRAFT. DO NOT APPLY until the database write path and migrations
-- 020-025 have been reconciled and the v22 SQL gates in
-- docs/schema/contracts/powerbi-fact-constellation-v22-design.md pass.
-- This migration preserves every v21 view and does not alter Silver data.
BEGIN;
SET LOCAL lock_timeout = '5s';

DO $$
BEGIN
    IF to_regclass('bronze.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'Migration 026 requires bronze.schema_migrations';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM bronze.schema_migrations WHERE version = 25
    ) THEN
        RAISE EXCEPTION 'Migration 026 requires migration 025';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_foreign_server WHERE srvname = 'srv_jobwant_yes123'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_namespace WHERE nspname = 'fdw_yes123'
    ) THEN
        RAISE EXCEPTION 'Migration 026 requires the existing yes123 FDW';
    END IF;
    IF to_regclass('fdw_yes123.latest_job_snapshots') IS NOT NULL
       OR to_regclass('fdw_yes123.latest_job_salary_observations') IS NOT NULL THEN
        RAISE EXCEPTION 'Migration 026 FDW projections already exist; inspect before proceeding';
    END IF;
END $$;

-- These projections target the verified yes123 Gold views, not raw Silver.
-- Their columns and types were inspected in jobwant_yes123 on 2026-10-10.
CREATE FOREIGN TABLE fdw_yes123.latest_job_snapshots (
    series_key text,
    snapshot_date date,
    batch_id text,
    job_no text,
    snapshot_datetime timestamp with time zone,
    cust_no text,
    area_key text,
    salary_low numeric,
    salary_high numeric,
    appear_date date,
    source_platform text,
    native_job_id text,
    source_job_key text
) SERVER srv_jobwant_yes123
OPTIONS (schema_name 'gold', table_name 'latest_job_snapshots');

CREATE FOREIGN TABLE fdw_yes123.latest_job_salary_observations (
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
OPTIONS (schema_name 'gold', table_name 'latest_job_salary_observations');

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM gold.latest_job_snapshots AS s
        WHERE COALESCE(s.source_platform, '104') = '104'
          AND (s.source_job_key IS NULL OR s.source_job_key NOT LIKE '104:%')
    ) OR EXISTS (
        SELECT 1
        FROM fdw_yes123.latest_job_snapshots AS s
        WHERE COALESCE(s.source_platform, 'yes123') = 'yes123'
          AND (s.source_job_key IS NULL OR s.source_job_key NOT LIKE 'yes123:%')
    ) THEN
        RAISE EXCEPTION 'Migration 026 requires complete platform-prefixed source_job_key values';
    END IF;
END $$;

CREATE VIEW gold.pbi_fact_job_daily_v22 AS
WITH snapshot_rows AS (
    SELECT COALESCE(s.source_platform, '104') AS source_platform,
           s.source_job_key, s.native_job_id, s.job_no,
           s.snapshot_date, s.snapshot_datetime, s.series_key, s.batch_id,
           s.cust_no, s.area_key, s.salary_low, s.salary_high, s.appear_date
    FROM gold.latest_job_snapshots AS s
    WHERE COALESCE(s.source_platform, '104') = '104'

    UNION ALL

    SELECT COALESCE(s.source_platform, 'yes123') AS source_platform,
           s.source_job_key, s.native_job_id, s.job_no,
           s.snapshot_date, s.snapshot_datetime, s.series_key, s.batch_id,
           s.cust_no, s.area_key, s.salary_low, s.salary_high, s.appear_date
    FROM fdw_yes123.latest_job_snapshots AS s
    WHERE COALESCE(s.source_platform, 'yes123') = 'yes123'
), keyed_rows AS (
    SELECT r.*,
           CASE
               WHEN r.cust_no IS NULL THEN NULL
               WHEN r.cust_no LIKE r.source_platform || ':%' THEN r.cust_no
               ELSE r.source_platform || ':' || r.cust_no
           END AS company_key,
           CASE
               WHEN r.area_key IS NULL THEN NULL
               ELSE r.source_platform || ':'
                    || encode(convert_to(r.area_key, 'UTF8'), 'hex')
           END AS scoped_area_key
    FROM snapshot_rows AS r
), daily_quality AS (
    SELECT r.source_job_key, r.snapshot_date,
           COUNT(*)::integer AS series_hit_count,
           COUNT(DISTINCT jsonb_build_array(
               r.company_key, r.scoped_area_key
           ))::integer AS context_variant_count,
           COUNT(DISTINCT jsonb_build_array(
               r.salary_low, r.salary_high, r.appear_date
           ))::integer AS attribute_variant_count
    FROM keyed_rows AS r
    GROUP BY r.source_job_key, r.snapshot_date
), representatives AS (
    SELECT DISTINCT ON (r.source_job_key, r.snapshot_date)
           r.*
    FROM keyed_rows AS r
    ORDER BY r.source_job_key, r.snapshot_date,
             r.snapshot_datetime DESC, r.series_key, r.batch_id DESC
)
SELECT
       r.source_platform AS "sourcePlatform",
       r.source_job_key AS "sourceJobKey",
       r.source_job_key AS "jobKey",
       r.native_job_id AS "nativeJobId",
       r.job_no AS "jobNo",
       r.cust_no AS "nativeCompanyId",
       r.area_key AS "nativeAreaKey",
       r.snapshot_date AS "snapshotDate",
       r.snapshot_datetime AT TIME ZONE 'Asia/Taipei' AS "snapshotDateTime",
       r.series_key AS "representativeSeriesKey",
       r.batch_id AS "representativeBatchId",
       r.company_key AS "companyKey",
       r.scoped_area_key AS "areaKey",
       r.salary_low AS "salaryLow",
       r.salary_high AS "salaryHigh",
       r.appear_date AS "appearDate",
       q.series_hit_count AS "seriesHitCount",
       q.context_variant_count AS "contextVariantCount",
       q.attribute_variant_count AS "attributeVariantCount",
       (q.context_variant_count > 1 OR q.attribute_variant_count > 1)
           AS "hasAttributeConflict"
FROM representatives AS r
JOIN daily_quality AS q
  ON q.source_job_key = r.source_job_key
 AND q.snapshot_date = r.snapshot_date;

CREATE VIEW gold.pbi_fact_salary_observations_v22 AS
WITH observation_rows AS (
    SELECT COALESCE(j.source_platform, '104') AS source_platform,
           j.source_job_key, j.native_job_id, j.job_no,
           j.cust_no AS native_company_id,
           j.area_key AS native_area_key,
           j.snapshot_date, j.snapshot_datetime,
           CASE
               WHEN j.cust_no IS NULL THEN NULL
               WHEN j.cust_no LIKE COALESCE(j.source_platform, '104') || ':%'
                   THEN j.cust_no
               ELSE COALESCE(j.source_platform, '104') || ':' || j.cust_no
           END AS company_key,
           CASE
               WHEN j.area_key IS NULL THEN NULL
               ELSE COALESCE(j.source_platform, '104') || ':'
                    || encode(convert_to(j.area_key, 'UTF8'), 'hex')
           END AS area_key,
           o.series_key, o.batch_id, o.source_kind, o.observation_index,
           o.raw_value_min, o.raw_value_max, o.amount_min, o.amount_max,
           o.currency_code, o.currency_basis, o.pay_period, o.range_kind,
           o.compensation_component, o.evidence_text,
           o.evidence_start, o.evidence_end, o.parse_status,
           o.quality_flags, o.confidence, o.parser_version
    FROM gold.latest_job_salary_observations AS o
    JOIN gold.latest_job_snapshots AS j
      ON j.series_key = o.series_key
     AND j.snapshot_date = o.snapshot_date
     AND j.batch_id = o.batch_id
     AND j.job_no = o.job_no
    WHERE COALESCE(j.source_platform, '104') = '104'

    UNION ALL

    SELECT COALESCE(j.source_platform, 'yes123') AS source_platform,
           j.source_job_key, j.native_job_id, j.job_no,
           j.cust_no AS native_company_id,
           j.area_key AS native_area_key,
           j.snapshot_date, j.snapshot_datetime,
           CASE
               WHEN j.cust_no IS NULL THEN NULL
               WHEN j.cust_no LIKE COALESCE(j.source_platform, 'yes123') || ':%'
                   THEN j.cust_no
               ELSE COALESCE(j.source_platform, 'yes123') || ':' || j.cust_no
           END AS company_key,
           CASE
               WHEN j.area_key IS NULL THEN NULL
               ELSE COALESCE(j.source_platform, 'yes123') || ':'
                    || encode(convert_to(j.area_key, 'UTF8'), 'hex')
           END AS area_key,
           o.series_key, o.batch_id, o.source_kind, o.observation_index,
           o.raw_value_min, o.raw_value_max, o.amount_min, o.amount_max,
           o.currency_code, o.currency_basis, o.pay_period, o.range_kind,
           o.compensation_component, o.evidence_text,
           o.evidence_start, o.evidence_end, o.parse_status,
           o.quality_flags, o.confidence, o.parser_version
    FROM fdw_yes123.latest_job_salary_observations AS o
    JOIN fdw_yes123.latest_job_snapshots AS j
      ON j.series_key = o.series_key
     AND j.snapshot_date = o.snapshot_date
     AND j.batch_id = o.batch_id
     AND j.job_no = o.job_no
    WHERE COALESCE(j.source_platform, 'yes123') = 'yes123'
), grouped_observations AS (
    SELECT r.source_platform, r.source_job_key, r.snapshot_date,
           r.source_kind, r.observation_index,
           COUNT(*)::integer AS series_hit_count,
           COUNT(DISTINCT jsonb_build_array(
               r.company_key, r.area_key
           ))::integer AS context_variant_count,
           COUNT(DISTINCT jsonb_build_array(
               r.raw_value_min, r.raw_value_max,
               r.amount_min, r.amount_max, r.currency_code,
               r.currency_basis, r.pay_period, r.range_kind,
               r.compensation_component, r.evidence_text,
               r.evidence_start, r.evidence_end, r.parse_status
           ))::integer AS conflict_value_count
    FROM observation_rows AS r
    GROUP BY r.source_platform, r.source_job_key, r.snapshot_date,
             r.source_kind, r.observation_index
), representatives AS (
    SELECT DISTINCT ON (
               r.source_platform, r.source_job_key, r.snapshot_date,
               r.source_kind, r.observation_index
           ) r.*
    FROM observation_rows AS r
    ORDER BY r.source_platform, r.source_job_key, r.snapshot_date,
             r.source_kind, r.observation_index,
             r.snapshot_datetime DESC, r.series_key, r.batch_id DESC
)
SELECT r.source_platform AS "sourcePlatform",
       r.source_job_key AS "sourceJobKey",
       r.source_job_key AS "jobKey",
       r.native_job_id AS "nativeJobId",
       r.job_no AS "jobNo",
       r.native_company_id AS "nativeCompanyId",
       r.native_area_key AS "nativeAreaKey",
       r.company_key AS "companyKey",
       r.area_key AS "areaKey",
       r.snapshot_date AS "snapshotDate",
       r.snapshot_datetime AT TIME ZONE 'Asia/Taipei' AS "snapshotDateTime",
       r.source_kind AS "sourceKind",
       r.observation_index AS "observationIndex",
       r.series_key AS "representativeSeriesKey",
       r.batch_id AS "representativeBatchId",
       r.raw_value_min AS "rawValueMin",
       r.raw_value_max AS "rawValueMax",
       r.amount_min AS "amountMin",
       r.amount_max AS "amountMax",
       btrim(r.currency_code::text) AS "currencyCode",
       r.currency_basis AS "currencyBasis",
       r.pay_period AS "payPeriod",
       r.range_kind AS "rangeKind",
       r.compensation_component AS "compensationComponent",
       r.evidence_text AS "evidenceText",
       r.evidence_start AS "evidenceStart",
       r.evidence_end AS "evidenceEnd",
       r.parse_status AS "parseStatus",
       r.quality_flags::text AS "qualityFlags",
       r.confidence AS "confidence",
       r.parser_version AS "parserVersion",
       g.series_hit_count AS "seriesHitCount",
       g.context_variant_count AS "contextVariantCount",
       g.context_variant_count > 1 AS "hasContextConflict",
       g.conflict_value_count AS "conflictValueCount",
       g.conflict_value_count > 1 AS "hasValueConflict"
FROM representatives AS r
JOIN grouped_observations AS g
  ON g.source_platform = r.source_platform
 AND g.source_job_key = r.source_job_key
 AND g.snapshot_date = r.snapshot_date
 AND g.source_kind = r.source_kind
 AND g.observation_index = r.observation_index;

CREATE VIEW gold.pbi_dim_job_v22 AS
WITH identity_rows AS (
    SELECT f.source_job_key, f.source_platform, f.native_job_id,
           f.job_no, f.snapshot_date
    FROM gold.pbi_fact_job_scope_v21 AS f

    UNION ALL

    SELECT f."sourceJobKey", f."sourcePlatform", f."nativeJobId",
           f."jobNo", f."snapshotDate"
    FROM gold.pbi_fact_job_daily_v22 AS f

    UNION ALL

    SELECT f."sourceJobKey", f."sourcePlatform", f."nativeJobId",
           f."jobNo", f."snapshotDate"
    FROM gold.pbi_fact_salary_observations_v22 AS f
), identity_summary AS (
    SELECT r.source_job_key,
           MIN(r.snapshot_date) AS first_observed_date,
           MAX(r.snapshot_date) AS last_observed_date,
           (
               COUNT(DISTINCT r.source_platform) > 1
               OR COUNT(DISTINCT r.native_job_id) > 1
               OR COUNT(DISTINCT r.job_no) > 1
           ) AS identity_conflict_flag
    FROM identity_rows AS r
    WHERE r.source_job_key IS NOT NULL
    GROUP BY r.source_job_key
), representative_identity AS (
    SELECT DISTINCT ON (r.source_job_key)
           r.source_job_key, r.source_platform, r.native_job_id, r.job_no
    FROM identity_rows AS r
    WHERE r.source_job_key IS NOT NULL
    ORDER BY r.source_job_key, r.snapshot_date DESC NULLS LAST,
             r.source_platform, r.native_job_id, r.job_no
), current_jobs AS (
    SELECT DISTINCT ON (f.source_job_key)
           f.source_job_key, f.job_name, f.job_link
    FROM gold.pbi_fact_job_scope_v21 AS f
    WHERE f.source_job_key IS NOT NULL
    ORDER BY f.source_job_key, f.snapshot_datetime DESC,
             f.series_key, f.batch_id DESC
)
SELECT i.source_job_key AS "jobKey",
       i.source_platform AS "sourcePlatform",
       i.native_job_id AS "nativeJobId",
       i.job_no AS "jobNo",
       c.job_name AS "currentJobName",
       c.job_link AS "currentJobLink",
       s.first_observed_date AS "firstObservedDate",
       s.last_observed_date AS "lastObservedDate",
       c.source_job_key IS NOT NULL AS "isCurrent",
       s.identity_conflict_flag AS "identityConflictFlag"
FROM representative_identity AS i
JOIN identity_summary AS s USING (source_job_key)
LEFT JOIN current_jobs AS c USING (source_job_key);

CREATE VIEW gold.pbi_fact_jobs_v22 AS
SELECT f.job_no AS "jobNo", f.cust_no AS "custNo",
       f.area_key AS "sourceAreaKey",
       CASE
           WHEN f.area_key IS NULL THEN NULL
           ELSE f.source_platform || ':'
                || encode(convert_to(f.area_key, 'UTF8'), 'hex')
       END AS "areaKey",
       CASE
           WHEN f.cust_no IS NULL THEN NULL
           WHEN f.cust_no LIKE f.source_platform || ':%' THEN f.cust_no
           ELSE f.source_platform || ':' || f.cust_no
       END AS "companyKey",
       f.source_job_key AS "jobKey",
       f.source_job_key AS "sourceJobKey", f.native_job_id AS "nativeJobId",
       f.source_platform AS "sourcePlatform", f.job_name AS "jobName",
       f.desc_snippet AS "descSnippet", f.job_address AS "jobAddress",
       f.job_addr_no_desc AS "jobAddrNoDesc", f.salary_low AS "salaryLow",
       f.salary_high AS "salaryHigh", f.appear_date AS "appearDate",
       f.job_link AS "jobLink", f.snapshot_date AS "snapshotDate",
       f.snapshot_datetime AS "snapshotDateTime",
       f.source_keyword AS "sourceKeyword", f.source_area AS "sourceArea"
FROM gold.pbi_fact_job_scope_v21 AS f;

CREATE VIEW gold.pbi_dim_company_v22 AS
WITH company_identity_rows AS (
    SELECT f."companyKey" AS company_key,
           f."sourcePlatform" AS source_platform,
           f."custNo" AS native_company_id,
           f."snapshotDate" AS snapshot_date
    FROM gold.pbi_fact_jobs_v22 AS f
    WHERE f."companyKey" IS NOT NULL

    UNION ALL

    SELECT f."companyKey", f."sourcePlatform",
           f."nativeCompanyId", f."snapshotDate"
    FROM gold.pbi_fact_job_daily_v22 AS f
    WHERE f."companyKey" IS NOT NULL

    UNION ALL

    SELECT f."companyKey", f."sourcePlatform",
           f."nativeCompanyId", f."snapshotDate"
    FROM gold.pbi_fact_salary_observations_v22 AS f
    WHERE f."companyKey" IS NOT NULL
), company_summary AS (
    SELECT r.company_key,
           (
               COUNT(DISTINCT r.source_platform) > 1
               OR COUNT(DISTINCT r.native_company_id) > 1
           ) AS identity_conflict_flag
    FROM company_identity_rows AS r
    GROUP BY r.company_key
), representative_company AS (
    SELECT DISTINCT ON (r.company_key)
           r.company_key, r.source_platform, r.native_company_id
    FROM company_identity_rows AS r
    ORDER BY r.company_key, r.snapshot_date DESC NULLS LAST,
             r.source_platform, r.native_company_id
), company_attribute_rows AS (
    SELECT '104'::text AS source_platform, c.cust_no AS native_company_id,
           c.company_name, c.co_industry, c.co_industry_desc, c.updated_at
    FROM silver.company_dimension AS c

    UNION ALL

    SELECT 'yes123'::text AS source_platform, c.cust_no AS native_company_id,
           c.company_name, c.co_industry, c.co_industry_desc, c.updated_at
    FROM fdw_yes123.company_dimension AS c
), company_attributes AS (
    SELECT DISTINCT ON (a.company_key)
           a.company_key, a.company_name, a.co_industry, a.co_industry_desc
    FROM (
        SELECT CASE
                   WHEN r.native_company_id LIKE r.source_platform || ':%'
                       THEN r.native_company_id
                   ELSE r.source_platform || ':' || r.native_company_id
               END AS company_key,
               r.company_name, r.co_industry, r.co_industry_desc, r.updated_at
        FROM company_attribute_rows AS r
        WHERE r.native_company_id IS NOT NULL
    ) AS a
    ORDER BY a.company_key, a.updated_at DESC NULLS LAST,
             a.company_name, a.co_industry_desc
), current_companies AS (
    SELECT DISTINCT f."companyKey" AS company_key
    FROM gold.pbi_fact_jobs_v22 AS f
    WHERE f."companyKey" IS NOT NULL
)
SELECT r.company_key AS "companyKey",
       r.source_platform AS "sourcePlatform",
       r.native_company_id AS "custNo",
       a.company_name AS "custName",
       a.co_industry AS "coIndustry",
       a.co_industry_desc AS "coIndustryDesc",
       c.company_key IS NOT NULL AS "isCurrent",
       s.identity_conflict_flag AS "identityConflictFlag"
FROM representative_company AS r
JOIN company_summary AS s USING (company_key)
LEFT JOIN company_attributes AS a USING (company_key)
LEFT JOIN current_companies AS c USING (company_key);

CREATE VIEW gold.pbi_dim_area_v22 AS
WITH area_rows AS (
    SELECT '104'::text AS source_platform,
           s.area_key AS native_area_key,
           s.snapshot_datetime, s.series_key, s.batch_id,
           a.job_addr_no, a.job_addr_no_desc, a.job_address,
           CASE
               WHEN a.latitude BETWEEN -90 AND 90
                    AND a.longitude BETWEEN -180 AND 180
                    AND NOT (a.latitude = 0 AND a.longitude = 0)
                   THEN a.latitude
               WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED')
                    AND g.latitude BETWEEN -90 AND 90
                    AND g.longitude BETWEEN -180 AND 180
                    AND NOT (g.latitude = 0 AND g.longitude = 0)
                   THEN g.latitude
           END AS lat,
           CASE
               WHEN a.latitude BETWEEN -90 AND 90
                    AND a.longitude BETWEEN -180 AND 180
                    AND NOT (a.latitude = 0 AND a.longitude = 0)
                   THEN a.longitude
               WHEN g.match_level IN ('EXACT_TEXT', 'ADDRESS_STANDARDIZED')
                    AND g.latitude BETWEEN -90 AND 90
                    AND g.longitude BETWEEN -180 AND 180
                    AND NOT (g.latitude = 0 AND g.longitude = 0)
                   THEN g.longitude
           END AS lon
    FROM gold.latest_job_snapshots AS s
    LEFT JOIN silver.area_dimension AS a USING (area_key)
    LEFT JOIN silver.address_geocodes AS g USING (area_key)
    WHERE COALESCE(s.source_platform, '104') = '104'
      AND s.area_key IS NOT NULL

    UNION ALL

    SELECT 'yes123'::text AS source_platform,
           s.area_key AS native_area_key,
           s.snapshot_datetime, s.series_key, s.batch_id,
           a.job_addr_no, a.job_addr_no_desc, a.job_address,
           CASE
               WHEN a.latitude BETWEEN -90 AND 90
                    AND a.longitude BETWEEN -180 AND 180
                    AND NOT (a.latitude = 0 AND a.longitude = 0)
                   THEN a.latitude
           END AS lat,
           CASE
               WHEN a.latitude BETWEEN -90 AND 90
                    AND a.longitude BETWEEN -180 AND 180
                    AND NOT (a.latitude = 0 AND a.longitude = 0)
                   THEN a.longitude
           END AS lon
    FROM fdw_yes123.latest_job_snapshots AS s
    LEFT JOIN fdw_yes123.area_dimension AS a USING (area_key)
    WHERE COALESCE(s.source_platform, 'yes123') = 'yes123'
      AND s.area_key IS NOT NULL
), representative_area AS (
    SELECT DISTINCT ON (r.source_platform, r.native_area_key)
           r.*
    FROM area_rows AS r
    ORDER BY r.source_platform, r.native_area_key,
             r.snapshot_datetime DESC, r.series_key, r.batch_id DESC
), area_with_county AS (
    SELECT r.*,
           ARRAY(
               SELECT DISTINCT CASE county_match.capture[1]
                   WHEN '台北市' THEN '臺北市'
                   WHEN '台中市' THEN '臺中市'
                   WHEN '台南市' THEN '臺南市'
                   WHEN '台東縣' THEN '臺東縣'
                   ELSE county_match.capture[1]
               END
               FROM regexp_matches(
                   concat_ws(' ', r.job_addr_no_desc, r.job_address),
                   '(臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|臺東縣|台東縣|花蓮縣|澎湖縣|金門縣|連江縣)',
                   'g'
               ) AS county_match(capture)
           ) AS matched_counties
    FROM representative_area AS r
)
SELECT r.source_platform || ':'
           || encode(convert_to(r.native_area_key, 'UTF8'), 'hex') AS "areaKey",
       r.source_platform AS "sourcePlatform",
       r.native_area_key AS "nativeAreaKey",
       r.job_addr_no AS "jobAddrNo",
       r.job_addr_no_desc AS "jobAddrNoDesc",
       r.job_address AS "jobAddress",
       CASE
           WHEN cardinality(r.matched_counties) = 1 THEN r.matched_counties[1]
           ELSE NULL
       END AS "jobCounty",
       r.lat, r.lon,
       CASE
           WHEN r.lat IS NULL OR r.lon IS NULL THEN '未判定'
           WHEN (r.lat BETWEEN 21.8 AND 25.5 AND r.lon BETWEEN 119.2 AND 122.1)
             OR (r.lat BETWEEN 24.3 AND 24.6 AND r.lon BETWEEN 118.1 AND 118.6)
             OR (r.lat BETWEEN 25.9 AND 26.5 AND r.lon BETWEEN 119.8 AND 120.2)
             OR (r.lat BETWEEN 20.5 AND 20.9 AND r.lon BETWEEN 116.4 AND 116.9)
             OR (r.lat BETWEEN 10.3 AND 10.5 AND r.lon BETWEEN 114.3 AND 114.5)
               THEN '國內'
           ELSE '國外(台灣地區之外)'
       END AS "jobLocationScope"
FROM area_with_county AS r;

CREATE VIEW gold.pbi_bridge_job_skill_v22 AS
SELECT f.source_job_key AS "jobKey",
       '104:' || s.skill_code AS "skillKey",
       '104'::text AS "sourcePlatform",
       s.skill_code AS "skillCode",
       MIN(d.skill_description) AS "skillDescription",
       COUNT(DISTINCT d.skill_description) > 1 AS "descriptionConflictFlag"
FROM silver.job_skill_snapshots AS s
JOIN gold.pbi_fact_job_scope_v21 AS f
  USING (series_key, snapshot_date, batch_id, job_no)
JOIN silver.skill_dimension AS d ON d.skill_code = s.skill_code
WHERE f.source_platform = '104'
GROUP BY f.source_job_key, s.skill_code;

CREATE VIEW gold.pbi_dim_skill_v22 AS
SELECT '104:' || d.skill_code AS "skillKey",
       '104'::text AS "sourcePlatform",
       d.skill_code AS "skillCode",
       MIN(d.skill_description) AS "skillDescription",
       COUNT(DISTINCT d.skill_description) > 1 AS "descriptionConflictFlag"
FROM silver.skill_dimension AS d
WHERE EXISTS (
    SELECT 1
    FROM gold.pbi_bridge_job_skill_v22 AS b
    WHERE b."skillCode" = d.skill_code
)
GROUP BY d.skill_code;

CREATE VIEW gold.pbi_bridge_job_category_v22 AS
WITH confirmed_category_map AS (
    SELECT c.source_platform, c.canonical_job_cat_code,
           MIN(c.native_category_code) AS native_category_code,
           MIN(c.native_category_name) AS native_category_name,
           MAX(c.match_confidence) AS match_confidence,
           COUNT(DISTINCT c.native_category_code) AS native_code_count
    FROM fdw_yes123.category_crosswalk AS c
    WHERE c.mapping_status = 'CONFIRMED'
    GROUP BY c.source_platform, c.canonical_job_cat_code
), category_rows AS (
    SELECT f.source_job_key AS job_key,
           f.source_platform,
           s.job_cat_code::text AS source_job_cat_code,
           s.job_cat_code::text AS native_job_cat_code,
           s.job_cat_code::text AS job_cat_identifier,
           d.job_cat_description,
           NULL::text AS mapping_status,
           NULL::numeric AS match_confidence
    FROM silver.job_category_snapshots AS s
    JOIN gold.pbi_fact_job_scope_v21 AS f
      USING (series_key, snapshot_date, batch_id, job_no)
    JOIN silver.category_dimension AS d USING (job_cat_code)
    WHERE f.source_platform = '104'

    UNION ALL

    SELECT f.source_job_key AS job_key,
           f.source_platform,
           s.job_cat_code::text AS source_job_cat_code,
           CASE WHEN m.native_code_count = 1
                THEN m.native_category_code
           END AS native_job_cat_code,
           CASE WHEN m.native_code_count = 1
                THEN m.native_category_code
                ELSE 'source:' || s.job_cat_code::text
           END AS job_cat_identifier,
           CASE WHEN m.native_code_count = 1
                THEN m.native_category_name
           END AS job_cat_description,
           CASE
               WHEN m.native_code_count = 1 THEN 'CONFIRMED'
               WHEN m.native_code_count > 1 THEN 'AMBIGUOUS_CONFIRMED'
               ELSE 'UNMAPPED'
           END::text AS mapping_status,
           CASE WHEN m.native_code_count = 1 THEN m.match_confidence END
               AS match_confidence
    FROM fdw_yes123.job_category_snapshots AS s
    JOIN gold.pbi_fact_job_scope_v21 AS f
      USING (series_key, snapshot_date, batch_id, job_no)
    LEFT JOIN confirmed_category_map AS m
      ON m.source_platform = f.source_platform
     AND m.canonical_job_cat_code = s.job_cat_code
    WHERE f.source_platform = 'yes123'
)
SELECT r.job_key AS "jobKey",
       r.source_platform || ':' || r.job_cat_identifier AS "jobCatKey",
       r.source_platform AS "sourcePlatform",
       COALESCE(r.native_job_cat_code, MIN(r.source_job_cat_code)) AS "jobCatCode",
       r.native_job_cat_code AS "nativeJobCatCode",
       MIN(r.source_job_cat_code) AS "sourceJobCatCode",
       MIN(r.job_cat_description) AS "jobCatDescription",
       MIN(r.mapping_status) AS "mappingStatus",
       MIN(r.match_confidence) AS "matchConfidence",
       COUNT(DISTINCT r.source_job_cat_code) > 1 AS "sourceCodeConflictFlag",
       COUNT(DISTINCT r.job_cat_description) > 1 AS "descriptionConflictFlag"
FROM category_rows AS r
GROUP BY r.job_key, r.source_platform, r.native_job_cat_code,
         r.job_cat_identifier;

CREATE VIEW gold.pbi_dim_job_category_v22 AS
SELECT r."jobCatKey",
       MIN(r."sourcePlatform") AS "sourcePlatform",
       MIN(r."jobCatCode") AS "jobCatCode",
       MIN(r."nativeJobCatCode") AS "nativeJobCatCode",
       MIN(r."sourceJobCatCode") AS "sourceJobCatCode",
       MIN(r."jobCatDescription") AS "jobCatDescription",
       MIN(r."mappingStatus") AS "mappingStatus",
       MIN(r."matchConfidence") AS "matchConfidence",
       COUNT(DISTINCT r."sourceJobCatCode") > 1 AS "sourceCodeConflictFlag",
       COUNT(DISTINCT r."jobCatDescription") > 1 AS "descriptionConflictFlag"
FROM gold.pbi_bridge_job_category_v22 AS r
GROUP BY r."jobCatKey";

INSERT INTO bronze.schema_migrations(version) VALUES (26)
ON CONFLICT (version) DO NOTHING;

COMMIT;
