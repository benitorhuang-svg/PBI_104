-- Migration 028: use current deduplicated jobs for v22 area dimensions.
-- The output contract and coordinate rules remain unchanged. v21 is preserved.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_dim_area_v22 AS
WITH area_rows AS (
    SELECT f."sourcePlatform" AS source_platform,
           f."sourceAreaKey" AS native_area_key,
           f."snapshotDateTime" AS snapshot_datetime,
           f."jobNo" AS tie_job_no,
           a.job_addr_no,
           COALESCE(f."jobAddrNoDesc", a.job_addr_no_desc) AS job_addr_no_desc,
           COALESCE(f."jobAddress", a.job_address) AS job_address,
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
    FROM gold.pbi_fact_jobs_v22 AS f
    LEFT JOIN silver.area_dimension AS a
      ON a.area_key = f."sourceAreaKey"
    LEFT JOIN silver.address_geocodes AS g
      ON g.area_key = f."sourceAreaKey"
    WHERE f."sourcePlatform" = '104'
      AND f."sourceAreaKey" IS NOT NULL

    UNION ALL

    SELECT f."sourcePlatform" AS source_platform,
           f."sourceAreaKey" AS native_area_key,
           f."snapshotDateTime" AS snapshot_datetime,
           f."jobNo" AS tie_job_no,
           a.job_addr_no,
           COALESCE(f."jobAddrNoDesc", a.job_addr_no_desc) AS job_addr_no_desc,
           COALESCE(f."jobAddress", a.job_address) AS job_address,
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
    FROM gold.pbi_fact_jobs_v22 AS f
    LEFT JOIN fdw_yes123.area_dimension AS a
      ON a.area_key = f."sourceAreaKey"
    WHERE f."sourcePlatform" = 'yes123'
      AND f."sourceAreaKey" IS NOT NULL
), representative_area AS (
    SELECT DISTINCT ON (r.source_platform, r.native_area_key)
           r.*
    FROM area_rows AS r
    ORDER BY r.source_platform, r.native_area_key,
             r.snapshot_datetime DESC, r.tie_job_no
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

INSERT INTO bronze.schema_migrations(version) VALUES (28)
ON CONFLICT (version) DO NOTHING;

COMMIT;
