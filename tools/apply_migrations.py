"""Plan or apply one sequential PostgreSQL migration with explicit write intent."""

import argparse
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from acquisition.platforms.jobwant_104.persistence.loader import read_db_config
from acquisition.shared.sql_parser import statements


MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[^/]+\.sql$")


def discover_migrations(directory):
    directory = directory.resolve()
    migrations = {}
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_NAME.match(path.name)
        if not match:
            continue
        text = path.read_text(encoding="utf-8")
        header = "\n".join(text.splitlines()[:12])
        migrations[int(match.group("version"))] = {
            "path": path,
            "relativePath": str(path.relative_to(PROJECT_ROOT)),
            "draft": "STATUS: DRAFT" in header or "DO NOT APPLY" in header,
            "statements": statements(text),
        }
    return migrations


def applied_versions(conn):
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        if conn.execute(
            "SELECT to_regclass('bronze.schema_migrations')"
        ).fetchone()[0] is None:
            return []
        return [
            row[0]
            for row in conn.execute(
                "SELECT version FROM bronze.schema_migrations ORDER BY version"
            ).fetchall()
        ]


def choose_target(applied, migrations, requested):
    if applied and applied != list(range(1, max(applied) + 1)):
        raise RuntimeError(
            "Migration history is not contiguous; inspect it before applying."
        )
    target = requested if requested is not None else max(applied, default=0) + 1
    if target not in migrations:
        raise RuntimeError(f"Migration {target:03d} is not present on disk.")
    expected = max(applied, default=0) + 1
    if target != expected:
        raise RuntimeError(
            f"Only the next migration may be applied: expected {expected:03d}, "
            f"received {target:03d}."
        )
    return target


def boundary_name(statement):
    without_header = re.sub(
        r"\A(?:\s*(?:--[^\n]*(?:\n|$)|/\*.*?\*/))*\s*",
        "",
        statement,
        flags=re.DOTALL,
    )
    return without_header.strip().upper().rstrip(";")


def execute_migration(conn, version, migration):
    executable = {
        boundary_name(item)
        for item in migration["statements"]
        if boundary_name(item) in {"BEGIN", "COMMIT"}
    }
    if "BEGIN" not in executable or "COMMIT" not in executable:
        raise RuntimeError(
            f"Migration {version:03d} must contain explicit BEGIN and COMMIT."
        )
    executed = 0
    with conn.transaction():
        conn.execute("SET LOCAL statement_timeout = '10min'")
        for index, statement in enumerate(migration["statements"], start=1):
            normalized = boundary_name(statement)
            if normalized in {"BEGIN", "COMMIT"}:
                continue
            try:
                conn.execute(statement)
            except Exception as error:
                raise RuntimeError(
                    f"Migration {version:03d} failed at statement {index}: {error}"
                ) from error
            executed += 1
    return executed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--version", type=int, help="One next migration to inspect/apply")
    parser.add_argument("--apply", action="store_true", help="Commit the migration")
    parser.add_argument(
        "--allow-draft",
        action="store_true",
        help="Acknowledge the migration header when applying a draft",
    )
    args = parser.parse_args(argv)
    try:
        migrations = discover_migrations(TOOLS / "sql" / "migrations")
        import psycopg

        with psycopg.connect(**read_db_config(args.env_file)) as conn:
            before = applied_versions(conn)
            version = choose_target(before, migrations, args.version)
            migration = migrations[version]
            if migration["draft"] and args.apply and not args.allow_draft:
                raise RuntimeError(
                    f"Migration {version:03d} is marked DRAFT; pass --allow-draft "
                    "only after its release gates have been reviewed."
                )
            result = {
                "database": conn.info.dbname,
                "version": version,
                "path": migration["relativePath"],
                "draft": migration["draft"],
                "statementCount": len(migration["statements"]),
                "appliedBefore": before,
                "mode": "apply" if args.apply else "dry-run",
            }
            if args.apply:
                result["executedStatements"] = execute_migration(
                    conn, version, migration
                )
                result["appliedAfter"] = applied_versions(conn)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"status": "ERROR", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
