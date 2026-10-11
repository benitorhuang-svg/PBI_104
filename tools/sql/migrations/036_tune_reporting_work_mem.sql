-- Migration 036: give the local reporting role enough sort memory for Gold reads.
-- The setting is scoped to jobwant_104 and does not alter rows or report semantics.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER ROLE pbi_admin IN DATABASE jobwant_104 SET work_mem = '128MB';

INSERT INTO bronze.schema_migrations(version) VALUES (36)
ON CONFLICT (version) DO NOTHING;

COMMIT;
