-- Migration 050: Publish governed platform dimension table and gold reader view.
-- Decouples analytical platform selection from fact table rows (OPT-06).
BEGIN;
SET LOCAL lock_timeout = '5s';

-- 1. Silver dimension table
CREATE TABLE IF NOT EXISTS silver.platform_dimension (
    platform_code character varying(32) PRIMARY KEY,
    platform_name character varying(64) NOT NULL,
    sort_order integer NOT NULL DEFAULT 1,
    is_analytics_enabled boolean NOT NULL DEFAULT true,
    is_acquisition_enabled boolean NOT NULL DEFAULT true
);

INSERT INTO silver.platform_dimension (platform_code, platform_name, sort_order, is_analytics_enabled, is_acquisition_enabled)
VALUES
    ('104', '104 人力銀行', 1, true, true),
    ('yes123', 'yes123 求職網', 2, true, true)
ON CONFLICT (platform_code) DO UPDATE
SET platform_name = EXCLUDED.platform_name,
    sort_order = EXCLUDED.sort_order,
    is_analytics_enabled = EXCLUDED.is_analytics_enabled,
    is_acquisition_enabled = EXCLUDED.is_acquisition_enabled;

-- 2. Gold reader view
CREATE OR REPLACE VIEW gold.pbi_dim_platform_v21 AS
SELECT
    platform_code AS "platformCode",
    platform_name AS "platformName",
    sort_order AS "sortOrder",
    is_analytics_enabled AS "isAnalyticsEnabled",
    is_acquisition_enabled AS "isAcquisitionEnabled"
FROM silver.platform_dimension;

INSERT INTO bronze.schema_migrations(version) VALUES (50)
ON CONFLICT (version) DO NOTHING;

COMMIT;
