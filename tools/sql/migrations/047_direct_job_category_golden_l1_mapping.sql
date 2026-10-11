-- Migration 047: Direct job category to Golden L1 mapping.
-- Maps yes123 native job categories directly to their corresponding
-- Golden L1 categories in silver.category_crosswalk, and ensures the
-- Golden L1 bridge reads local silver crosswalk via pbi_fact_job_scope_v21.
BEGIN;
SET LOCAL lock_timeout = '5s';

-- 1. Batch update all 574 yes123 native categories to their Golden L1 canonical category
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2002000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 行政／總務／法務類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1001_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2003000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 財會／金融專業類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1002_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2001000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 經營／人資類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1003_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2005000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 客服／門市／業務／貿易類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1004_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2006000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 餐飲／旅遊 ／美容美髮類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1005_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2004000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 行銷／企劃／專案管理類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1006_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2013000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 傳播藝術／設計類' WHERE source_platform = 'yes123' AND (native_category_code LIKE '2_1007_0001%' OR native_category_code LIKE '2_1007_0002%');
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2014000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 文字／傳媒工作類' WHERE source_platform = 'yes123' AND (native_category_code LIKE '2_1007_0003%' OR native_category_code LIKE '2_1007_0004%');
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2012000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 營建／製圖類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1008_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2008000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 研發相關類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1009_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2009000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 生產製造／品管／環衛類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1010_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2007000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 資訊軟體系統類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1011_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2010000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 操作／技術／維修類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1012_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2011000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 資材／物流／運輸類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1013_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2015000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 醫療／保健服務類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1014_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2016000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 學術／教育／輔導類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1015_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2017000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 軍警消／保全類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1016_%';
UPDATE silver.category_crosswalk SET canonical_job_cat_code = 2018000000, mapping_status = 'CONFIRMED', match_confidence = 1.00, notes = 'Direct mapping to Golden L1: 其他職類' WHERE source_platform = 'yes123' AND native_category_code LIKE '2_1017_%';

-- 2. Optimize gold.pbi_bridge_job_category_golden_v22 to read local silver crosswalk directly from scope
CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_golden_v22 AS
WITH source_assignments AS (
    SELECT f.job_no AS "jobNo",
           f.source_platform AS "sourcePlatform",
           s.job_cat_code::text AS "nativeCategoryCode",
           d.job_cat_description AS "nativeCategoryName",
           s.job_cat_code AS "canonicalJobCatCode",
           'CONFIRMED'::text AS "mappingStatus",
           1.00::numeric AS "matchConfidence"
    FROM silver.job_category_snapshots AS s
    JOIN gold.pbi_fact_job_scope_v21 AS f
      USING (series_key, snapshot_date, batch_id, job_no)
    JOIN silver.category_dimension AS d
      USING (job_cat_code)
    WHERE f.source_platform = '104'

    UNION ALL

    SELECT f.job_no AS "jobNo",
           f.source_platform AS "sourcePlatform",
           f.source_jobcat AS "nativeCategoryCode",
           c.native_category_name AS "nativeCategoryName",
           c.canonical_job_cat_code AS "canonicalJobCatCode",
           COALESCE(c.mapping_status, 'BLOCKED') AS "mappingStatus",
           COALESCE(c.match_confidence, 0.00)::numeric AS "matchConfidence"
    FROM gold.pbi_fact_job_scope_v21 AS f
    LEFT JOIN silver.category_crosswalk AS c
      ON c.source_platform = 'yes123'
     AND c.native_category_code = f.source_jobcat
    WHERE f.source_platform = 'yes123'
      AND f.source_jobcat IS NOT NULL
),
resolved_assignments AS (
    SELECT a.*,
           d.job_cat_description AS "canonicalJobCatName",
           l1.job_cat_code AS "goldenL1Code",
           l1.job_cat_description AS "goldenL1Name"
    FROM source_assignments AS a
    LEFT JOIN silver.category_dimension AS d
      ON d.job_cat_code = a."canonicalJobCatCode"
    LEFT JOIN silver.category_dimension AS l1
      ON l1.job_cat_code::text = d.path_codes ->> 0
)
SELECT DISTINCT "jobNo",
       "sourcePlatform",
       "nativeCategoryCode",
       "nativeCategoryName",
       "canonicalJobCatCode",
       "canonicalJobCatName",
       "mappingStatus",
       "matchConfidence",
       "goldenL1Code",
       "goldenL1Name"
FROM resolved_assignments;

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_v21 AS
SELECT DISTINCT g."jobNo",
       COALESCE(g."canonicalJobCatCode", -1::bigint) AS "jobCatCode",
       COALESCE(g."canonicalJobCatName", '未映射來源職類') AS "jobCatDescription"
FROM gold.pbi_bridge_job_category_golden_v22 AS g;

CREATE OR REPLACE VIEW gold.pbi_bridge_job_category_keys_v21 AS
SELECT DISTINCT "jobNo", "jobCatCode"
FROM gold.pbi_bridge_job_category_v21;

INSERT INTO bronze.schema_migrations(version) VALUES (47)
ON CONFLICT (version) DO NOTHING;

COMMIT;
