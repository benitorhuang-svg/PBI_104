"""Apply the local PostgreSQL schema and idempotent migrations."""

from pathlib import Path

from .sql_parser import statements


def apply_schema(conn, schema_path):
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
