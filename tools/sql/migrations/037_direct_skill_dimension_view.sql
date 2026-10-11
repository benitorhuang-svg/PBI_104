-- Migration 037: avoid rebuilding the skill bridge for the small skill dimension.
-- The direct source set is verified equal to the existing v21 Gold view.
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE OR REPLACE VIEW gold.pbi_dim_skill_v21 AS
SELECT skill_code AS "skillCode",
       skill_description AS "skillDescription"
FROM silver.skill_dimension;

INSERT INTO bronze.schema_migrations(version) VALUES (37)
ON CONFLICT (version) DO NOTHING;

COMMIT;
