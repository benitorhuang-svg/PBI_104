-- Migration 033: optimize pbi_dim_company_v21 and pbi_dim_date_v21 for instant sub-second refresh.
-- Eliminates full table scans and multi-layer distinct-on sorts across 195k fact rows.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_dim_company_v21 AS
SELECT DISTINCT ON (c.cust_no)
       c.cust_no AS "custNo",
       c.company_name AS "custName",
       c.co_industry AS "coIndustry",
       c.co_industry_desc AS "coIndustryDesc"
FROM (
    SELECT cust_no, company_name, co_industry, co_industry_desc, 1 AS priority
    FROM silver.company_dimension
    UNION ALL
    SELECT cust_no, company_name, co_industry, co_industry_desc, 2 AS priority
    FROM fdw_yes123.company_dimension
) c
ORDER BY c.cust_no, c.priority;

CREATE OR REPLACE VIEW gold.pbi_dim_date_v21 AS
WITH local_today AS (
    SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Taipei')::date AS today
), bounds AS (
    SELECT '2024-01-01'::date AS start_date,
           (date_trunc('year', t.today::timestamp with time zone) + '1 year'::interval - '1 day'::interval)::date AS end_date
    FROM local_today t
), calendar AS (
    SELECT generate_series(bounds.start_date::timestamp with time zone, bounds.end_date::timestamp with time zone, '1 day'::interval)::date AS calendar_date
    FROM bounds
)
SELECT calendar_date AS "Date",
       EXTRACT(year FROM calendar_date)::integer AS "Year",
       EXTRACT(month FROM calendar_date)::integer AS "MonthNo",
       to_char(calendar_date::timestamp with time zone, 'YYYY-MM') AS "Month",
       EXTRACT(quarter FROM calendar_date)::integer AS "QuarterNo",
       'Q' || EXTRACT(quarter FROM calendar_date)::integer::text AS "Quarter",
       EXTRACT(day FROM calendar_date)::integer AS "Day"
FROM calendar;

INSERT INTO bronze.schema_migrations(version) VALUES (33)
ON CONFLICT (version) DO NOTHING;

COMMIT;
