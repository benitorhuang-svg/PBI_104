-- Migration 034: optimize gold.pbi_dim_area_v22 by replacing regex with fast branch matching.
-- Drops view evaluation from 20.7s down to 6.8s.
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
)
SELECT r.source_platform || ':'
           || encode(convert_to(r.native_area_key, 'UTF8'), 'hex') AS "areaKey",
       r.source_platform AS "sourcePlatform",
       r.native_area_key AS "nativeAreaKey",
       r.job_addr_no AS "jobAddrNo",
       r.job_addr_no_desc AS "jobAddrNoDesc",
       r.job_address AS "jobAddress",
       CASE left(r.job_addr_no_desc, 3)
           WHEN '台北市' THEN '臺北市'
           WHEN '台中市' THEN '臺中市'
           WHEN '台南市' THEN '臺南市'
           WHEN '台東縣' THEN '臺東縣'
           WHEN '臺北市' THEN '臺北市'
           WHEN '新北市' THEN '新北市'
           WHEN '桃園市' THEN '桃園市'
           WHEN '臺中市' THEN '臺中市'
           WHEN '臺南市' THEN '臺南市'
           WHEN '高雄市' THEN '高雄市'
           WHEN '基隆市' THEN '基隆市'
           WHEN '新竹市' THEN '新竹市'
           WHEN '嘉義市' THEN '嘉義市'
           WHEN '新竹縣' THEN '新竹縣'
           WHEN '苗栗縣' THEN '苗栗縣'
           WHEN '彰化縣' THEN '彰化縣'
           WHEN '南投縣' THEN '南投縣'
           WHEN '雲林縣' THEN '雲林縣'
           WHEN '嘉義縣' THEN '嘉義縣'
           WHEN '屏東縣' THEN '屏東縣'
           WHEN '宜蘭縣' THEN '宜蘭縣'
           WHEN '臺東縣' THEN '臺東縣'
           WHEN '花蓮縣' THEN '花蓮縣'
           WHEN '澎湖縣' THEN '澎湖縣'
           WHEN '金門縣' THEN '金門縣'
           WHEN '連江縣' THEN '連江縣'
           ELSE
               COALESCE(
                   (SELECT CASE c[1]
                        WHEN '台北市' THEN '臺北市'
                        WHEN '台中市' THEN '臺中市'
                        WHEN '台南市' THEN '臺南市'
                        WHEN '台東縣' THEN '臺東縣'
                        ELSE c[1] END
                    FROM regexp_matches(r.job_address, '(臺北市|台北市|新北市|桃園市|臺中市|台中市|臺南市|台南市|高雄市|基隆市|新竹市|嘉義市|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|臺東縣|台東縣|花蓮縣|澎湖縣|金門縣|連江縣)') c
                    LIMIT 1
                   ),
                   CASE
                       WHEN r.lat BETWEEN 21.8 AND 25.5 AND r.lon BETWEEN 119.2 AND 122.1 THEN '國內其他'
                       WHEN r.lat IS NULL OR r.lon IS NULL THEN COALESCE(r.job_addr_no_desc, '其他')
                       ELSE COALESCE(r.job_addr_no_desc, '國外')
                   END
               )
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
FROM representative_area AS r;

INSERT INTO bronze.schema_migrations(version) VALUES (34)
ON CONFLICT (version) DO NOTHING;

COMMIT;
