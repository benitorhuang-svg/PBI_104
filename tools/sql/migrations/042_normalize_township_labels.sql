-- Migration 042: normalize malformed township labels without altering source address evidence.
-- Keep the migration output on the existing pbi_dim_area_v22 contract so Power BI
-- continues to read the same view and column names.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER VIEW gold.pbi_dim_area_v22 RENAME TO pbi_dim_area_v22_raw;

CREATE VIEW gold.pbi_dim_area_v22 AS
WITH prepared AS (
    SELECT r.*,
           CASE
               WHEN r."jobTownship" IS NULL THEN NULL
               WHEN r."jobCounty" IS NOT NULL
                    AND left(btrim(r."jobTownship"), length(r."jobCounty")) = r."jobCounty"
                   THEN NULLIF(substring(btrim(r."jobTownship") FROM length(r."jobCounty") + 1), '')
               ELSE NULLIF(btrim(r."jobTownship"), '')
           END AS township_input
    FROM gold.pbi_dim_area_v22_raw AS r
), normalized AS (
    SELECT p.*,
           CASE
               WHEN p.township_input IS NULL THEN NULL
               WHEN p.township_input LIKE '%全區%'
                 OR p.township_input IN ('市', '縣') THEN NULL
               WHEN p.township_input IN ('阿里山', '三地門', '太麻里')
                   THEN p.township_input
               ELSE (
                   regexp_match(
                       p.township_input,
                       '^.{1,6}?(?:區|鄉|鎮(?!區)|市(?!區))'
                   )
               )[1]
           END AS normalized_township
    FROM prepared AS p
)
SELECT n."areaKey",
       n."sourcePlatform",
       n."nativeAreaKey",
       n."jobAddrNo",
       n."jobAddrNoDesc",
       n."jobAddress",
       n."jobCounty",
       n.lat,
       n.lon,
       n."jobLocationScope",
       n."jobRegion",
       n.normalized_township AS "jobTownship"
FROM normalized AS n;

INSERT INTO bronze.schema_migrations(version) VALUES (42)
ON CONFLICT (version) DO NOTHING;

COMMIT;
