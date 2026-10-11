"""Apply the local PostgreSQL schema and idempotent migrations."""

from pathlib import Path

from .sql_parser import statements

BASE_SCHEMA_VERSION = 19


def _legacy_write_block_reason(conn):
    current = conn.execute("""SELECT to_regclass('bronze.schema_migrations')""").fetchone()[0]
    if current is None:
        return None
    version = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM bronze.schema_migrations"
    ).fetchone()[0]
    protected = conn.execute("""
        SELECT to_regclass('gold.pbi_fact_jobs_v21'),
               to_regclass('fdw_yes123.job_snapshots')
    """).fetchone()
    if version > BASE_SCHEMA_VERSION:
        return f"database migration is {version}; legacy schema is {BASE_SCHEMA_VERSION}"
    if any(protected):
        return "federated Gold or yes123 FDW objects are present"
    return None


def apply_schema(conn, schema_path):
    block_reason = _legacy_write_block_reason(conn)
    if block_reason:
        raise RuntimeError(
            "Refusing to apply init_postgres_schema.sql to a protected database: "
            f"{block_reason}. Reconcile the authoritative migration runner first."
        )
    prior_type = conn.execute("""SELECT format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute AS a JOIN pg_class AS c ON c.oid = a.attrelid
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'silver' AND c.relname = 'area_dimension'
          AND a.attname = 'job_addr_no' AND NOT a.attisdropped""").fetchone()
    prior_area_type = prior_type[0] if prior_type else None
    if prior_area_type == "integer":
        view = conn.execute("SELECT to_regclass('gold.latest_observed_jobs')").fetchone()[0]
        if view:
            conn.execute("DROP VIEW gold.latest_observed_jobs")
    sql = Path(schema_path).read_text(encoding="utf-8")
    area_type_migration = "alter table silver.area_dimension alter column job_addr_no type bigint"
    for statement in statements(sql):
        migration = statement.strip().lower()
        if migration == area_type_migration and prior_area_type == "bigint":
            continue
        if migration:
            conn.execute(statement)
