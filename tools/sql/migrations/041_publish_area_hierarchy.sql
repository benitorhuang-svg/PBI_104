-- Migration 041: publish a strict Taiwan county/township hierarchy.
-- The existing generic area label is retained as jobRegion so foreign and
-- source-native labels remain available to the report.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_dim_area_v22 AS
WITH current_area_jobs AS (
    SELECT DISTINCT ON (f."sourcePlatform", f."sourceAreaKey")
           f."sourcePlatform" AS source_platform,
           f."sourceAreaKey" AS native_area_key,
           f."snapshotDateTime" AS snapshot_datetime,
           f."jobNo" AS tie_job_no,
           f."jobAddrNoDesc" AS job_addr_no_desc,
           f."jobAddress" AS job_address
    FROM gold.pbi_fact_jobs_v22 AS f
    WHERE f."sourceAreaKey" IS NOT NULL
    ORDER BY f."sourcePlatform", f."sourceAreaKey",
             f."snapshotDateTime" DESC, f."jobNo"
), area_rows AS (
    SELECT f.source_platform,
           f.native_area_key,
           f.snapshot_datetime,
           f.tie_job_no,
           a.job_addr_no,
           COALESCE(f.job_addr_no_desc, a.job_addr_no_desc, f.job_address, a.job_address) AS job_addr_no_desc,
           COALESCE(f.job_address, a.job_address) AS job_address,
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
    FROM current_area_jobs AS f
    LEFT JOIN silver.area_dimension AS a
      ON a.area_key = f.native_area_key
    LEFT JOIN silver.address_geocodes AS g
      ON g.area_key = f.native_area_key
    WHERE f.source_platform = '104'

    UNION ALL

    SELECT f.source_platform,
           f.native_area_key,
           f.snapshot_datetime,
           f.tie_job_no,
           a.job_addr_no,
           COALESCE(f.job_addr_no_desc, a.job_addr_no_desc, f.job_address, a.job_address) AS job_addr_no_desc,
           COALESCE(f.job_address, a.job_address) AS job_address,
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
    FROM current_area_jobs AS f
    LEFT JOIN fdw_yes123.area_dimension AS a
      ON a.area_key = f.native_area_key
    WHERE f.source_platform = 'yes123'
), representative_area AS (
    SELECT DISTINCT ON (r.source_platform, r.native_area_key)
           r.*
    FROM area_rows AS r
    ORDER BY r.source_platform, r.native_area_key,
             r.snapshot_datetime DESC, r.tie_job_no
), county_labeled AS (
    SELECT r.*,
           COALESCE(
               (
                   SELECT CASE c[1]
                       WHEN '台北市' THEN '臺北市'
                       WHEN '台中市' THEN '臺中市'
                       WHEN '台南市' THEN '臺南市'
                       WHEN '台東縣' THEN '臺東縣'
                       ELSE c[1]
                   END
                   FROM regexp_matches(
                       r.job_addr_no_desc,
                       '^(臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|臺東縣|台東縣|花蓮縣|澎湖縣|金門縣|連江縣)'
                   ) AS c
                   LIMIT 1
               ),
               (
                   SELECT CASE c[1]
                       WHEN '台北市' THEN '臺北市'
                       WHEN '台中市' THEN '臺中市'
                       WHEN '台南市' THEN '臺南市'
                       WHEN '台東縣' THEN '臺東縣'
                       ELSE c[1]
                   END
                   FROM regexp_matches(
                       r.job_address,
                       '(臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|臺東縣|台東縣|花蓮縣|澎湖縣|金門縣|連江縣)'
                   ) AS c
                   LIMIT 1
               )
           ) AS job_county,
           CASE
               WHEN r.job_addr_no_desc ~ '^(臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|臺東縣|台東縣|花蓮縣|澎湖縣|金門縣|連江縣)'
                   THEN r.job_addr_no_desc
               WHEN r.job_address ~ '^(臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|臺東縣|台東縣|花蓮縣|澎湖縣|金門縣|連江縣)'
                   THEN r.job_address
           END AS township_source
    FROM representative_area AS r
), classified_area AS (
    SELECT c.*,
           CASE
               WHEN c.job_county IS NOT NULL THEN c.job_county
               WHEN c.lat BETWEEN 21.8 AND 25.5 AND c.lon BETWEEN 119.2 AND 122.1 THEN '國內其他'
               WHEN c.lat IS NULL OR c.lon IS NULL THEN COALESCE(c.job_addr_no_desc, '其他')
               ELSE COALESCE(c.job_addr_no_desc, '國外')
           END AS job_region,
           NULLIF(
               btrim(
                   regexp_replace(
                       c.township_source,
                       '^(臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|臺東縣|台東縣|花蓮縣|澎湖縣|金門縣|連江縣)',
                       ''
                   )
               ),
               ''
           ) AS job_township
    FROM county_labeled AS c
)
SELECT c.source_platform || ':'
           || encode(convert_to(c.native_area_key, 'UTF8'), 'hex') AS "areaKey",
       c.source_platform AS "sourcePlatform",
       c.native_area_key AS "nativeAreaKey",
       c.job_addr_no AS "jobAddrNo",
       c.job_addr_no_desc AS "jobAddrNoDesc",
       c.job_address AS "jobAddress",
       c.job_county AS "jobCounty",
       c.lat,
       c.lon,
       CASE
           WHEN c.lat IS NULL OR c.lon IS NULL THEN
               CASE
                   WHEN c.job_county IN (
                       '臺北市', '新北市', '桃園市', '臺中市', '臺南市', '高雄市',
                       '基隆市', '新竹市', '嘉義市', '新竹縣', '苗栗縣', '彰化縣',
                       '南投縣', '雲林縣', '嘉義縣', '屏東縣', '宜蘭縣', '花蓮縣',
                       '臺東縣', '澎湖縣', '金門縣', '連江縣'
                   ) THEN '國內'
                   WHEN c.job_region LIKE '東南亞%'
                     OR c.job_region LIKE '東北亞%'
                     OR c.job_region LIKE '中歐%'
                     OR c.job_region LIKE '中美洲%'
                     OR c.job_region LIKE '美中地區%'
                       THEN '國外(台灣地區之外)'
                   ELSE '未判定'
               END
           WHEN (c.lat BETWEEN 21.8 AND 25.5 AND c.lon BETWEEN 119.2 AND 122.1)
             OR (c.lat BETWEEN 24.3 AND 24.6 AND c.lon BETWEEN 118.1 AND 118.6)
             OR (c.lat BETWEEN 25.9 AND 26.5 AND c.lon BETWEEN 119.8 AND 120.2)
             OR (c.lat BETWEEN 20.5 AND 20.9 AND c.lon BETWEEN 116.4 AND 116.9)
             OR (c.lat BETWEEN 10.3 AND 10.5 AND c.lon BETWEEN 114.3 AND 114.5)
               THEN '國內'
           ELSE '國外(台灣地區之外)'
       END AS "jobLocationScope",
       c.job_region AS "jobRegion",
       c.job_township AS "jobTownship"
FROM classified_area AS c;

INSERT INTO bronze.schema_migrations(version) VALUES (41)
ON CONFLICT (version) DO NOTHING;

COMMIT;
