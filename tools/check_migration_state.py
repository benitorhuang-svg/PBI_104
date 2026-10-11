"""Report PostgreSQL migration and v22 release-gate state without writes."""

import argparse
import json
from pathlib import Path
import re
import sys

TOOLS = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from acquisition.platforms.jobwant_104.persistence.loader import read_db_config


MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[^/]+\.sql$")


def discover_migrations(directory):
    migrations = {}
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_NAME.match(path.name)
        if not match:
            continue
        text = path.read_text(encoding="utf-8")
        header = "\n".join(text.splitlines()[:12])
        migrations[int(match.group("version"))] = {
            "path": str(path.relative_to(PROJECT_ROOT)),
            "draft": "STATUS: DRAFT" in header or "DO NOT APPLY" in header,
        }
    return migrations


def inspect_database(conn):
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        database = conn.execute(
            "SELECT current_database(), to_regclass('bronze.schema_migrations')"
        ).fetchone()
        if database[1] is None:
            applied_versions = []
        else:
            applied_versions = [
                row[0] for row in conn.execute(
                    "SELECT version FROM bronze.schema_migrations ORDER BY version"
                ).fetchall()
            ]
        objects = conn.execute("""
            SELECT object_name, to_regclass(object_name)
            FROM (VALUES
                ('gold.pbi_fact_jobs_v21'),
                ('gold.pbi_fact_jobs_v22'),
                ('gold.pbi_dim_area_v21'),
                ('gold.pbi_dim_area_v22'),
                ('gold.pbi_bridge_job_category_keys_v21'),
                ('gold.pbi_bridge_job_skill_keys_v21'),
                ('gold.pbi_fact_jobs_report_v22'),
                ('fdw_yes123.job_snapshots'),
                ('fdw_yes123.latest_job_snapshots')
            ) AS requested(object_name)
            ORDER BY object_name
        """).fetchall()
    return {
        "database": database[0],
        "appliedVersions": applied_versions,
        "maxAppliedVersion": max(applied_versions, default=0),
        "objects": {
            name: {"present": relation is not None, "relation": relation}
            for name, relation in objects
        },
    }


def build_report(database, migrations):
    applied = set(database["appliedVersions"])
    available = sorted(migrations)
    pending = [version for version in available if version not in applied]
    first_tracked_version = min(available, default=0)
    missing_on_disk = sorted(
        version
        for version in applied
        if version >= first_tracked_version and version not in migrations
    )
    history_contiguous = database["appliedVersions"] == list(
        range(1, database["maxAppliedVersion"] + 1)
    )
    pending_drafts = [
        version for version in pending if migrations[version]["draft"]
    ]
    protected = database["maxAppliedVersion"] > 19 or any(
        database["objects"][name]["present"]
        for name in ("gold.pbi_fact_jobs_v21", "fdw_yes123.job_snapshots")
    )
    v22_objects = all(
        database["objects"][name]["present"]
        for name in (
            "gold.pbi_fact_jobs_v22",
            "gold.pbi_dim_area_v22",
            "gold.pbi_bridge_job_category_keys_v21",
            "gold.pbi_bridge_job_skill_keys_v21",
            "gold.pbi_fact_jobs_report_v22",
        )
    )
    return {
        **database,
        "availableMigrations": {
            str(version): migrations[version] for version in available
        },
        "pendingVersions": pending,
        "pendingDraftVersions": pending_drafts,
        "appliedVersionsMissingOnDisk": missing_on_disk,
        "migrationHistoryContiguous": history_contiguous,
        "legacyWriteBlocked": protected,
        "v22ObjectsPresent": v22_objects,
        "status": (
            "READY"
            if not pending_drafts
            and not missing_on_disk
            and history_contiguous
            and v22_objects
            else "BLOCKED"
        ),
        "nextAction": (
            "Reconcile migration files/history and pass the v22 release gates."
            if pending_drafts or missing_on_disk or not history_contiguous or not v22_objects
            else "Run the v22 model contract and Desktop refresh gates."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--require-ready", action="store_true",
                        help="Return exit code 1 while the release gate is blocked")
    args = parser.parse_args(argv)
    try:
        migrations = discover_migrations(TOOLS / "sql" / "migrations")
        import psycopg

        with psycopg.connect(**read_db_config(args.env_file)) as conn:
            report = build_report(inspect_database(conn), migrations)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if args.require_ready and report["status"] != "READY" else 0
    except Exception as error:
        print(json.dumps({"status": "ERROR", "error": str(error)},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
